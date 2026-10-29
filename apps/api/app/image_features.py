"""Offline visual encoders. Neither encoder trains on query/gallery data."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import warnings

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 5 * 1024 * 1024
COLOR_VERSION = "hsv8x4x4-hellinger-v1"
DEEP_VERSION = "resnet18-imagenet1k-v1-avgpool-l2-v1"
OFFICIAL_SHA256 = "f37072fd47e89c5e827621c5baffa7500819f7896bbacec160b1a16c560e07ec"


class ImageInputError(ValueError):
    def __init__(self, code, message, status=422):
        self.code, self.message, self.status = code, message, status


class SearchUnavailable(RuntimeError):
    pass


def decode_image(raw):
    if len(raw) > MAX_BYTES:
        raise ImageInputError("FILE_TOO_LARGE", "参考图片不能超过 5 MB", 413)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("format")
                if min(image.size) < 32 or image.width * image.height > 20_000_000:
                    raise ValueError("size")
                image.load()
                return ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ImageInputError("INVALID_IMAGE", "请上传有效 JPG、PNG 或 WebP，短边至少 32 像素且不超过 2000 万像素") from None


def color_vector(image):
    hsv = np.asarray(image.resize((128,128), Image.Resampling.BILINEAR).convert("HSV"), dtype=np.int32)
    bins = (hsv[:,:,0]//32)*16 + (hsv[:,:,1]//64)*4 + hsv[:,:,2]//64
    histogram = np.bincount(bins.ravel(), minlength=128).astype(np.float32)
    return np.sqrt(histogram / histogram.sum())


class ResnetEncoder:
    def __init__(self, weights_path: Path):
        if not weights_path.is_file():
            raise SearchUnavailable("尚未准备 ResNet18 权重，请先运行本地权重准备命令")
        self.weights_sha256 = sha256(weights_path.read_bytes()).hexdigest()
        if self.weights_sha256 != OFFICIAL_SHA256:
            raise SearchUnavailable("预训练权重校验失败，请重新准备官方权重")
        try:
            import torch
            from torchvision.models import resnet18, ResNet18_Weights
            torch.set_num_threads(min(4, torch.get_num_threads()))
            self.torch = torch
            model = resnet18(weights=None)
            model.load_state_dict(torch.load(weights_path, map_location="cpu", weights_only=True))
            model.fc = torch.nn.Identity()
            self.model = model.eval().cpu()
            self.transform = ResNet18_Weights.IMAGENET1K_V1.transforms()
            self.runtime = {"torch":torch.__version__, "device":"cpu", "threads":torch.get_num_threads()}
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            raise SearchUnavailable("视觉模型加载失败，请检查图搜依赖和官方权重") from exc

    def encode(self, image):
        with self.torch.inference_mode():
            vector = self.model(self.transform(image).unsqueeze(0))[0].numpy().astype(np.float32)
        norm = np.linalg.norm(vector)
        if not np.isfinite(vector).all() or norm <= 0:
            raise SearchUnavailable("视觉模型未产生有效特征")
        return vector / norm
