import sys
from pathlib import Path

# Asegura que el paquete app/ sea importable sin depender de cómo se invoque
# pytest (por ejemplo, si se corre desde otro directorio o vía un IDE).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
