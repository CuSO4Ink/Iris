from __future__ import annotations

import argparse
import csv
import json
import math
import random
import tempfile
import warnings
from pathlib import Path

import onnx
import torch
import torch.nn.functional as F
from PIL import Image, ImageChops, ImageStat
from torch import nn
from torch.utils.data import DataLoader, Dataset


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
LOSS_NAMES = ("teacher", "blocks", "structure", "texture", "palette", "flatness")


class ResidualBlock(nn.Module):
    def __init__(self, channels: int, dilation: int = 1):
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv2d(channels, channels, 3, padding=dilation, dilation=dilation),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, channels, 3, padding=dilation, dilation=dilation),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.relu(x + self.body(x))


class Student(nn.Module):
    def __init__(self, channels: int = 48, blocks: int = 4, wide_context: bool = False):
        super().__init__()
        hidden = channels * 2
        head = [
            nn.Conv2d(3, channels, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, hidden, 3, stride=2, padding=1),
            nn.ReLU(inplace=True),
        ]
        if wide_context:
            head += [nn.Conv2d(hidden, hidden, 3, stride=2, padding=1), nn.ReLU(inplace=True)]
        self.head = nn.Sequential(*head)
        dilations = (1, 2, 4, 8, 4, 2) if wide_context else (1,)
        self.body = nn.Sequential(*(ResidualBlock(hidden, dilations[index % len(dilations)]) for index in range(blocks)))
        self.scale = 4.0 if wide_context else 2.0
        self.tail = nn.Sequential(
            nn.Conv2d(hidden, channels, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, 3, 3, padding=1),
        )
        nn.init.zeros_(self.tail[-1].weight)
        nn.init.zeros_(self.tail[-1].bias)

    def forward(self, source: torch.Tensor) -> torch.Tensor:
        features = self.body(self.head(source))
        features = F.interpolate(features, scale_factor=self.scale, mode="bilinear", align_corners=False)
        delta = 0.5 * torch.tanh(self.tail(features))
        return torch.clamp(source + delta, 0.0, 1.0)


def image_index(folder: Path) -> dict[str, Path]:
    if not folder.is_dir():
        raise FileNotFoundError(f"Missing image folder: {folder}")
    result: dict[str, Path] = {}
    for path in sorted(folder.rglob("*")):
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        key = path.relative_to(folder).with_suffix("").as_posix().lower()
        if key in result:
            raise ValueError(f"Duplicate pair key '{key}' in {folder}")
        result[key] = path
    return result


def image_tensor(image: Image.Image) -> torch.Tensor:
    image = image.convert("RGB")
    width, height = image.size
    values = torch.frombuffer(bytearray(image.tobytes()), dtype=torch.uint8)
    return values.reshape(height, width, 3).permute(2, 0, 1).float().div_(255.0)


class PairDataset(Dataset):
    def __init__(
        self,
        root: Path,
        crop_size: int,
        training: bool,
        repeats: int = 1,
        focus_candidates: int = 1,
        focus_probability: float = 1.0,
    ):
        sources = image_index(root / "input")
        targets = image_index(root / "target")
        missing_targets = sorted(sources.keys() - targets.keys())
        missing_sources = sorted(targets.keys() - sources.keys())
        if missing_targets or missing_sources:
            raise ValueError(
                f"Unpaired files in {root}: "
                f"missing targets={missing_targets[:5]}, missing inputs={missing_sources[:5]}"
            )
        if not sources:
            raise ValueError(f"No paired images found in {root}")
        self.pairs = [(sources[key], targets[key]) for key in sorted(sources)]
        self.crop_size = crop_size
        self.training = training
        self.repeats = repeats
        self.focus_candidates = focus_candidates
        self.focus_probability = focus_probability

    def __len__(self) -> int:
        return len(self.pairs) * self.repeats

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        source_path, target_path = self.pairs[index % len(self.pairs)]
        with Image.open(source_path) as source_image, Image.open(target_path) as target_image:
            source = source_image.convert("RGB")
            target = target_image.convert("RGB")
        if source.size != target.size:
            raise ValueError(f"Pair dimensions differ: {source_path}={source.size}, {target_path}={target.size}")
        width, height = source.size
        size = self.crop_size
        if width < size or height < size:
            raise ValueError(f"Image is smaller than crop_size={size}: {source_path}={source.size}")
        if self.training:
            boxes = []
            candidates = self.focus_candidates if random.random() < self.focus_probability else 1
            for _ in range(candidates):
                left = random.randint(0, width - size)
                top = random.randint(0, height - size)
                boxes.append((left, top, left + size, top + size))
            box = max(
                boxes,
                key=lambda candidate: sum(ImageStat.Stat(ImageChops.difference(source.crop(candidate), target.crop(candidate))).mean),
            )
        else:
            left = (width - size) // 2
            top = (height - size) // 2
            box = (left, top, left + size, top + size)
        source = source.crop(box)
        target = target.crop(box)
        if self.training and random.random() < 0.5:
            source = source.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            target = target.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        return image_tensor(source), image_tensor(target)


def sobel(image: torch.Tensor) -> torch.Tensor:
    gray = 0.299 * image[:, 0:1] + 0.587 * image[:, 1:2] + 0.114 * image[:, 2:3]
    kernel_x = gray.new_tensor(((-1, 0, 1), (-2, 0, 2), (-1, 0, 1))).reshape(1, 1, 3, 3)
    kernel_y = kernel_x.transpose(2, 3)
    dx = F.conv2d(gray, kernel_x, padding=1)
    dy = F.conv2d(gray, kernel_y, padding=1)
    return torch.sqrt(dx.square() + dy.square() + 1e-6)


def palette_tensor(colors: list[str], device: torch.device) -> torch.Tensor:
    values = []
    for color in colors:
        if len(color) != 7 or not color.startswith("#"):
            raise ValueError(f"Palette color must be #RRGGBB: {color}")
        values.append([int(color[i : i + 2], 16) / 255.0 for i in (1, 3, 5)])
    return torch.tensor(values, device=device).reshape(1, len(values), 3, 1, 1)


def flatness_loss(output: torch.Tensor, source: torch.Tensor, threshold: float) -> torch.Tensor:
    flat = (sobel(source).detach() < threshold).to(output.dtype)
    dx = (output[:, :, :, 1:] - output[:, :, :, :-1]).abs().mean(1, keepdim=True)
    dy = (output[:, :, 1:, :] - output[:, :, :-1, :]).abs().mean(1, keepdim=True)
    mask_x = flat[:, :, :, 1:]
    mask_y = flat[:, :, 1:, :]
    loss_x = (dx * mask_x).sum() / mask_x.sum().clamp_min(1.0)
    loss_y = (dy * mask_y).sum() / mask_y.sum().clamp_min(1.0)
    return 0.5 * (loss_x + loss_y)


def loss_terms(
    output: torch.Tensor,
    source: torch.Tensor,
    target: torch.Tensor,
    palette: torch.Tensor,
    flat_edge_threshold: float,
) -> dict[str, torch.Tensor]:
    output_blur = F.avg_pool2d(output, 5, stride=1, padding=2)
    target_blur = F.avg_pool2d(target, 5, stride=1, padding=2)
    palette_distance = (output[:, None] - palette).abs().mean(2).amin(1).mean()
    return {
        "teacher": F.l1_loss(output, target),
        "blocks": F.l1_loss(F.avg_pool2d(output, 16, 16), F.avg_pool2d(target, 16, 16)),
        "structure": F.l1_loss(sobel(output), sobel(source)),
        "texture": F.l1_loss(output - output_blur, target - target_blur),
        "palette": palette_distance,
        "flatness": flatness_loss(output, source, flat_edge_threshold),
    }


def load_config(path: Path) -> tuple[dict, Path]:
    path = path.resolve()
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    crop_size = int(config["data"]["crop_size"])
    export_size = int(config["export"]["size"])
    if crop_size < 32 or crop_size % 2 or export_size < 32 or export_size % 2:
        raise ValueError("crop_size and export size must be even integers >= 32")
    if config["model"].get("wide_context") and (crop_size % 4 or export_size % 4):
        raise ValueError("wide_context requires crop_size and export size divisible by 4")
    weights = config["loss"]
    missing = [name for name in LOSS_NAMES if name not in weights]
    if missing or not any(float(weights[name]) > 0 for name in LOSS_NAMES):
        raise ValueError(f"Loss config is incomplete or all zero; missing={missing}")
    if not config["style"]["palette"]:
        raise ValueError("style.palette must contain at least one color")
    return config, path.parent


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def save_tensor(path: Path, tensor: torch.Tensor) -> None:
    tensor = tensor.detach().clamp(0, 1).mul(255).round().byte().cpu()
    tensor = tensor.permute(1, 2, 0).contiguous()
    height, width, _ = tensor.shape
    image = Image.frombytes("RGB", (width, height), bytes(tensor.reshape(-1).tolist()))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def save_preview(path: Path, source: torch.Tensor, target: torch.Tensor, output: torch.Tensor) -> None:
    save_tensor(path, torch.cat((source[0], target[0], output[0]), dim=2))


def run_loader(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    config: dict,
    palette: torch.Tensor,
    optimizer: torch.optim.Optimizer | None = None,
    scaler: torch.amp.GradScaler | None = None,
) -> tuple[dict[str, float], tuple[torch.Tensor, torch.Tensor, torch.Tensor]]:
    training = optimizer is not None
    model.train(training)
    totals = {"total": 0.0, **{name: 0.0 for name in LOSS_NAMES}}
    count = 0
    preview = None
    amp = bool(config["train"]["amp"]) and device.type == "cuda"
    context = torch.enable_grad() if training else torch.no_grad()
    with context:
        for source, target in loader:
            source = source.to(device, non_blocking=True)
            target = target.to(device, non_blocking=True)
            if training:
                optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=amp):
                output = model(source)
                terms = loss_terms(
                    output,
                    source,
                    target,
                    palette,
                    float(config["style"]["flat_edge_threshold"]),
                )
                loss = sum(float(config["loss"][name]) * terms[name] for name in LOSS_NAMES)
            if training:
                assert scaler is not None
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
            batch = source.shape[0]
            count += batch
            totals["total"] += float(loss.detach()) * batch
            for name in LOSS_NAMES:
                totals[name] += float(terms[name].detach()) * batch
            preview = (source[:1].cpu(), target[:1].cpu(), output[:1].detach().cpu())
    assert preview is not None
    return {name: value / count for name, value in totals.items()}, preview


def checkpoint_payload(
    model: Student,
    optimizer: torch.optim.Optimizer,
    config: dict,
    epoch: int,
    best_loss: float,
) -> dict:
    return {
        "model_state": model.state_dict(),
        "optimizer_state": optimizer.state_dict(),
        "model": config["model"],
        "epoch": epoch,
        "best_loss": best_loss,
    }


def train(config_path: Path, resume: Path | None) -> None:
    config, root = load_config(config_path)
    seed = int(config["train"]["seed"])
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = Student(**config["model"]).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=float(config["train"]["learning_rate"]))
    use_amp = bool(config["train"]["amp"]) and device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    start_epoch = 1
    best_loss = math.inf
    if resume:
        state = torch.load(resume, map_location=device, weights_only=True)
        if state["model"] != config["model"]:
            raise ValueError("Cannot resume after changing model.channels or model.blocks; start a new run")
        model.load_state_dict(state["model_state"])
        optimizer.load_state_dict(state["optimizer_state"])
        for group in optimizer.param_groups:
            group["lr"] = float(config["train"]["learning_rate"])
        start_epoch = int(state["epoch"]) + 1
        best_loss = float(state["best_loss"])

    crop_size = int(config["data"]["crop_size"])
    repeats = int(config["data"].get("repeats", 1))
    focus_candidates = int(config["data"].get("focus_candidates", 1))
    focus_probability = float(config["data"].get("focus_probability", 1.0))
    if repeats < 1 or focus_candidates < 1 or not 0.0 <= focus_probability <= 1.0:
        raise ValueError("repeats/focus_candidates must be >= 1 and focus_probability in [0, 1]")
    train_set = PairDataset(
        resolve(root, config["data"]["train"]),
        crop_size,
        training=True,
        repeats=repeats,
        focus_candidates=focus_candidates,
        focus_probability=focus_probability,
    )
    val_set = PairDataset(resolve(root, config["data"]["val"]), crop_size, training=False)
    workers = int(config["train"]["workers"])
    loader_args = {
        "batch_size": int(config["train"]["batch_size"]),
        "num_workers": workers,
        "pin_memory": device.type == "cuda",
        "persistent_workers": workers > 0,
    }
    train_loader = DataLoader(train_set, shuffle=True, **loader_args)
    val_loader = DataLoader(val_set, shuffle=False, **loader_args)
    palette = palette_tensor(config["style"]["palette"], device)
    output_dir = resolve(root, config["train"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "config.snapshot.json").open("w", encoding="utf-8") as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)
    metrics_path = output_dir / "metrics.csv"
    if not resume:
        with metrics_path.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(
                ("epoch",) + tuple(f"train_{name}" for name in ("total",) + LOSS_NAMES)
                + tuple(f"val_{name}" for name in ("total",) + LOSS_NAMES)
            )

    print(f"device={device}, train_pairs={len(train_set)}, val_pairs={len(val_set)}")
    epochs = int(config["train"]["epochs"])
    for epoch in range(start_epoch, epochs + 1):
        train_metrics, _ = run_loader(model, train_loader, device, config, palette, optimizer, scaler)
        val_metrics, preview = run_loader(model, val_loader, device, config, palette)
        with metrics_path.open("a", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(
                (epoch,)
                + tuple(train_metrics[name] for name in ("total",) + LOSS_NAMES)
                + tuple(val_metrics[name] for name in ("total",) + LOSS_NAMES)
            )
        if epoch % int(config["train"]["preview_every"]) == 0 or epoch == 1:
            save_preview(output_dir / f"preview_{epoch:04d}.png", *preview)
        is_best = val_metrics["total"] < best_loss
        best_loss = min(best_loss, val_metrics["total"])
        payload = checkpoint_payload(model, optimizer, config, epoch, best_loss)
        torch.save(payload, output_dir / "last.pt")
        if is_best:
            torch.save(payload, output_dir / "best.pt")
        print(
            f"epoch={epoch:03d} train={train_metrics['total']:.5f} "
            f"val={val_metrics['total']:.5f} best={best_loss:.5f}"
        )


def write_onnx(model: nn.Module, dummy: torch.Tensor, destination: Path, opset: int) -> None:
    # ponytail: keep the simple legacy graph until UE NNE compatibility is re-verified with the new exporter.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="You are using the legacy TorchScript-based ONNX export.*")
        torch.onnx.export(
            model,
            (dummy,),
            destination,
            input_names=["scene_color"],
            output_names=["stylized_color"],
            opset_version=opset,
            dynamo=False,
            external_data=False,
        )


def export_onnx(config_path: Path, checkpoint_override: Path | None = None) -> Path:
    config, root = load_config(config_path)
    checkpoint = checkpoint_override or resolve(root, config["export"]["checkpoint"])
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    model = Student(**state["model"])
    model.load_state_dict(state["model_state"])
    model.eval()
    size = int(config["export"]["size"])
    destination = resolve(root, config["export"]["onnx"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    dummy = torch.zeros(1, 3, size, size)
    write_onnx(model, dummy, destination, int(config["export"]["opset"]))
    exported = onnx.load(destination)
    onnx.checker.check_model(exported)
    dimensions = [item.dim_value for item in exported.graph.input[0].type.tensor_type.shape.dim]
    if dimensions != [1, 3, size, size]:
        raise RuntimeError(f"Unexpected ONNX input shape: {dimensions}")
    print(f"onnx={destination}, bytes={destination.stat().st_size}, input={dimensions}")
    return destination


def smoke() -> None:
    torch.manual_seed(1)
    model = Student(channels=16, blocks=1)
    source = torch.rand(1, 3, 64, 64)
    target = torch.rand_like(source)
    palette = palette_tensor(["#0B1F26", "#D9793E", "#F2D6A2"], torch.device("cpu"))
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    output = model(source)
    terms = loss_terms(output, source, target, palette, 0.08)
    loss = sum(terms.values())
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    assert output.shape == source.shape and torch.isfinite(loss)
    checked = output.detach()
    assert 0.0 <= float(checked.min()) <= float(checked.max()) <= 1.0
    assert Student(channels=16, blocks=2, wide_context=True)(source).shape == source.shape
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "smoke.onnx"
        write_onnx(model.eval(), source, path, 17)
        onnx.checker.check_model(onnx.load(path))
    print(f"smoke=ok, loss={float(loss.detach()):.5f}, output_shape={list(output.shape)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal paired distillation trainer for UE Neural Render Lab")
    commands = parser.add_subparsers(dest="command", required=True)
    train_command = commands.add_parser("train")
    train_command.add_argument("config", type=Path)
    train_command.add_argument("--resume", type=Path)
    export_command = commands.add_parser("export")
    export_command.add_argument("config", type=Path)
    export_command.add_argument("--checkpoint", type=Path)
    commands.add_parser("smoke")
    args = parser.parse_args()
    if args.command == "train":
        train(args.config, args.resume)
    elif args.command == "export":
        export_onnx(args.config, args.checkpoint)
    else:
        smoke()


if __name__ == "__main__":
    main()
