#***REngine Begin Modify added by tuckersu. [7DRGS ImprovedGS helper ops: GC/MU/EAS score]
import torch


def compute_current_budget(iteration: int, opt) -> int:
    """Compute ImprovedGS GC budget with sqrt warmup."""
    final_budget = int(getattr(opt, "final_budget", 600000))
    budget = int(getattr(opt, "budget", 0))
    budget_multiplier = float(getattr(opt, "budget_multiplier", 3.0))
    max_budget = budget if budget > 0 else max(int(final_budget * budget_multiplier), final_budget)

    densify_start = int(getattr(opt, "densify_from_iter", 500))
    warmup_offset = int(getattr(opt, "budget_warmup_until_offset", 500))
    densify_end = int(getattr(opt, "densify_until_iter", 15000)) - warmup_offset
    if densify_end <= densify_start:
        return max_budget

    progress = (float(iteration) - float(densify_start)) / float(densify_end - densify_start)
    progress = min(max(progress, 0.0), 1.0)
    if progress >= 1.0:
        return max_budget
    return max(int((progress ** 0.5) * max_budget), 1)


def should_run_parameter_update(iteration: int, opt, use_mu: bool) -> bool:
    """ImprovedGS MU update skipping schedule."""
    if not use_mu:
        return True
    mu_start_iter = int(getattr(opt, "mu_start_iter", 20000))
    mu_interval = max(int(getattr(opt, "mu_interval", 5)), 1)
    mu_second_start_iter = int(getattr(opt, "mu_second_start_iter", 25000))
    mu_second_interval = max(int(getattr(opt, "mu_second_interval", 10)), 1)

    if iteration < mu_start_iter:
        return True
    if iteration < mu_second_start_iter:
        return (iteration % mu_interval) == 0
    return (iteration % mu_second_interval) == 0


def normalize_to_unit_range(value_tensor: torch.Tensor) -> torch.Tensor:
    sanitized = torch.nan_to_num(value_tensor.detach().float(), nan=0.0, posinf=0.0, neginf=0.0)
    if sanitized.numel() == 0:
        return sanitized
    min_value = sanitized.amin()
    max_value = sanitized.amax()
    scale = max_value - min_value
    if float(scale.item()) <= 0.0:
        return torch.zeros_like(sanitized)
    return (sanitized - min_value) / scale
#***REngine End Modify
