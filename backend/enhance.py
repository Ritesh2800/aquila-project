"""Zero-DCE++ low-light enhancement."""
import importlib.util
import cv2
import numpy as np
import torch
import config

device = "cuda" if torch.cuda.is_available() else "cpu"
_net = None


def get_zdce():
    global _net
    if _net is not None:
        return _net
    model_py = config.ZD_DIR / "model.py"
    weights = config.ZD_DIR / "snapshots_Zero_DCE++" / "Epoch99.pth"
    if not model_py.exists() or not weights.exists():
        raise RuntimeError(f"Zero-DCE++ not found in {config.ZD_DIR}. Run setup.sh first.")
    spec = importlib.util.spec_from_file_location("zdce_model", model_py)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        net = mod.enhance_net_nopool(config.ZD_SCALE)
    except TypeError:
        net = mod.enhance_net_nopool()
    net = net.to(device)
    state = torch.load(weights, map_location=device)
    state = {k.replace("module.", "", 1): v for k, v in state.items()}
    net.load_state_dict(state)
    _net = net.eval()
    return _net


def _pick_enhanced(outs, x):
    if torch.is_tensor(outs):
        return outs
    if config.ZD_OUT_INDEX is not None:
        return outs[config.ZD_OUT_INDEX]
    same = [o for o in outs if torch.is_tensor(o) and o.shape == x.shape]
    return same[0] if same else outs[0]


@torch.no_grad()
def enhance_bgr(frame_bgr):
    """Brighten one BGR frame (numpy uint8) and return a BGR frame."""
    net, s = get_zdce(), config.ZD_SCALE
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    x = torch.from_numpy(rgb).float().div(255).permute(2, 0, 1).unsqueeze(0).to(device)
    h, w = x.shape[2], x.shape[3]
    x = x[:, :, : (h // s) * s, : (w // s) * s]
    y = _pick_enhanced(net(x), x).clamp(0, 1).squeeze(0).permute(1, 2, 0).cpu().numpy()
    out = cv2.cvtColor((y * 255 + 0.5).astype(np.uint8), cv2.COLOR_RGB2BGR)
    if out.shape[:2] != frame_bgr.shape[:2]:
        out = cv2.resize(out, (frame_bgr.shape[1], frame_bgr.shape[0]))
    return out
