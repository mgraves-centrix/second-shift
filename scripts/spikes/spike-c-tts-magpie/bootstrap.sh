#!/usr/bin/env bash
# Spike rung 2b: conda env pinned to Python 3.12 (NeMo dep ceiling is <3.14).
set -x
D=$HOME/spikes/tts-magpie
export PIP_DISABLE_PIP_VERSION_CHECK=1
echo "=== STEP conda-env ==="
"$D/conda/bin/conda" create -y -p "$D/env312" python=3.12 || exit 1
P="$D/env312/bin/python"
"$P" -V
echo "=== STEP header-check ==="
ls -l "$D/env312/include/python3.12/Python.h" || exit 1
echo "=== STEP torch ==="
"$P" -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu130 || exit 1
echo "=== STEP pyopenjtalk ==="
"$P" -m pip install pyopenjtalk || exit 1
echo "=== STEP nemo-main ==="
"$P" -m pip install "nemo_toolkit[tts] @ git+https://github.com/NVIDIA/NeMo.git@main"
echo "=== STEP nemo-verify ==="
"$P" -c "import nemo; print('NEMOVER', nemo.__version__)"
"$P" -c "from nemo.collections.tts.models import MagpieTTSModel; print('MAGPIE_IMPORT_OK')"
echo "=== STEP cuda-verify ==="
"$P" -c "import torch; print('TORCHCUDA', torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
echo "=== DONE rc=$? ==="
