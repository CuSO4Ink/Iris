#***REngine Begin Modify added by tuckersu. [Edge map utils for EAS scoring in 7DRGS]
import torch
import torch.nn.functional as F


_FIND_EDGES_KERNEL = torch.tensor(
    [[[-1.0, -1.0, -1.0], [-1.0, 8.0, -1.0], [-1.0, -1.0, -1.0]]],
    dtype=torch.float32,
).unsqueeze(0)


def _normalize_to_unit(edge: torch.Tensor) -> torch.Tensor:
    e_min = edge.amin()
    e_max = edge.amax()
    if float((e_max - e_min).item()) <= 0.0:
        return torch.zeros_like(edge)
    return (edge - e_min) / (e_max - e_min)


def compute_edge_map(image_chw: torch.Tensor, alpha_mask: torch.Tensor = None) -> torch.Tensor:
    """Compute Laplacian edge map from [3,H,W] image; output [H,W] in [0,1]."""
    img = image_chw[:3].detach().to(torch.float32).unsqueeze(0)
    rgb_255 = torch.round(img * 255.0)
    gray = torch.round(
        (299.0 * rgb_255[:, 0:1] + 587.0 * rgb_255[:, 1:2] + 114.0 * rgb_255[:, 2:3]) / 1000.0
    )
    kernel = _FIND_EDGES_KERNEL.to(device=img.device, dtype=torch.float32)
    edge = F.conv2d(gray, kernel, padding=1).clamp(0.0, 255.0) / 255.0
    edge = _normalize_to_unit(edge.squeeze(0).squeeze(0))
    if alpha_mask is not None:
        mask_hw = alpha_mask.detach().to(edge.device, dtype=torch.float32).squeeze(0)
        edge = edge * (mask_hw > 0.5).to(edge.dtype)
    return edge
#***REngine End Modify
