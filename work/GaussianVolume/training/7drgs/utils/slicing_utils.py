#***REngine Begin Modify added by tuckersu. [Add 7DGS slicing and covariance utility functions]
import torch


def strip_lower_diag(matrix: torch.Tensor) -> torch.Tensor:
    """Extract 6-parameter covariance representation from batched 3x3 matrices."""
    return torch.stack([
        matrix[:, 0, 0].abs(),
        matrix[:, 0, 1],
        matrix[:, 0, 2],
        matrix[:, 1, 1].abs(),
        matrix[:, 1, 2],
        matrix[:, 2, 2].abs(),
    ], dim=1)


def safe_inverse(matrix: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    """Safely compute matrix inverse with numerical stabilization fallback."""
    if matrix.shape[-1] != matrix.shape[-2]:
        raise ValueError("safe_inverse expects square matrices")

    stabilized = matrix
    eye = torch.eye(matrix.shape[-1], dtype=matrix.dtype, device=matrix.device)
    stabilized = stabilized + eps * eye.unsqueeze(0)

    try:
        return torch.linalg.inv(stabilized)
    except RuntimeError:
        return torch.linalg.pinv(stabilized)


def create_cholesky(diag: torch.Tensor, l_triang: torch.Tensor) -> torch.Tensor:
    """Build covariance matrix Sigma = L*L^T from batched Cholesky parameters."""
    l_matrix = torch.diag_embed(diag)
    n_dim = diag.size(1)
    tril_indices = torch.tril_indices(n_dim, n_dim, offset=-1, device=diag.device)
    l_matrix[:, tril_indices[0], tril_indices[1]] = (
        l_triang.view(diag.size(0), -1) * diag[:, tril_indices[0]]
    )
    return torch.bmm(l_matrix, l_matrix.transpose(-1, -2))


def slice_gaussian_dynamic(
    mu_p: torch.Tensor,
    mu_t: torch.Tensor,
    mu_d: torch.Tensor,
    t: torch.Tensor,
    d: torch.Tensor,
    sigma: torch.Tensor,
    lambda_t: torch.Tensor,
    lambda_d: torch.Tensor,
    eps: float = 1e-6,
):
    """Slice 7D Gaussian (p,t,d) to conditional 3D Gaussian under observation (t,d)."""
    sigma_p = sigma[..., :3, :3]
    sigma_ptd = sigma[..., :3, 3:]
    sigma_td_block = sigma[..., 3:, 3:]

    sigma_td_inv = safe_inverse(sigma_td_block, eps=eps)
    sigma_d_inv = sigma_td_inv[..., 1:, 1:]
    sigma_t_inv = sigma_td_inv[..., 0, 0]

    sigma_regr = torch.matmul(sigma_ptd, sigma_td_inv)
    sigma_ptd_tp = sigma_ptd.transpose(-2, -1)
    sigma_cond = sigma_p - torch.matmul(sigma_regr, sigma_ptd_tp)

    t_diff = (t - mu_t).squeeze(-1)
    d_diff = d - mu_d

    cond_diff = torch.cat([t_diff.unsqueeze(-1), d_diff], dim=-1).unsqueeze(-1)
    mu_cond = mu_p + torch.bmm(sigma_regr, cond_diff).squeeze(-1)

    lambda_t_term = lambda_t.squeeze(-1) if lambda_t.ndim > 1 else lambda_t
    lambda_d_term = lambda_d.squeeze(-1) if lambda_d.ndim > 1 else lambda_d

    log_f_cond_t = -lambda_t_term * t_diff * sigma_t_inv * t_diff
    log_f_cond_d = -lambda_d_term * torch.einsum("bi,bij,bj->b", d_diff, sigma_d_inv, d_diff)
    # Match the UE runtime's AlphaCond = opacity * sqrt(exp(-0.5 * λq)).
    f_cond = torch.exp(0.25 * (log_f_cond_t + log_f_cond_d)).unsqueeze(-1)

    return mu_cond, strip_lower_diag(sigma_cond), f_cond
#***REngine End Modify
