"""Copy an already available official checkpoint; never download at API runtime."""
import argparse
from hashlib import sha256
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--source',type=Path,default=Path.home()/'.cache/torch/hub/checkpoints/resnet18-f37072fd.pth')
args=parser.parse_args()
source=args.source
if not source.is_file():
    raise SystemExit('No cached checkpoint. Obtain the official resnet18-f37072fd.pth and pass --source PATH. See M4 documentation.')
digest=sha256(source.read_bytes()).hexdigest()
if digest!='f37072fd47e89c5e827621c5baffa7500819f7896bbacec160b1a16c560e07ec':
    raise SystemExit('Official checkpoint checksum prefix mismatch; no file copied')
target=ROOT/'apps/api/.local/models'/source.name
target.parent.mkdir(parents=True,exist_ok=True)
if target.exists() and sha256(target.read_bytes()).hexdigest()!=digest:
    raise SystemExit('Different existing checkpoint; refusing to overwrite')
if not target.exists():
    shutil.copyfile(source,target)
print('Ready:',target)
print('SHA256:',digest)
