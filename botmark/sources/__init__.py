import time
from typing import Any, Optional, Dict, Mapping
from pathlib import Path

class BotmarkSource:

    def __init__( self ):
        pass

    def list_models( self ):
        pass

    def load_botmark(self, model_id):
        pass

class StringSource(BotmarkSource):
    """
    Minimal in-memory source:
    - pass a single (model_id, markdown) OR a dict mapping ids -> markdown strings
    - list_models() returns the same envelope as FileSystemSource
    - load_botmark(model_id) returns the stored markdown or None
    """
    def __init__(self,
                 model_id: Optional[str] = None,
                 text: Optional[str] = None,
                 models: Optional[Mapping[str, str]] = None) -> None:
        super().__init__()

        if models is not None and (model_id is not None or text is not None):
            raise ValueError("Provide EITHER `models` OR (`model_id` and `text`).")

        if models is not None:
            self._models: Dict[str, str] = dict(models)
        else:
            if not model_id or text is None:
                raise ValueError("Provide `model_id` and `text` for single-model usage.")
            self._models = {model_id: text}

        # give everything a created timestamp now
        now = int(time.time())
        self._created: Dict[str, int] = {mid: now for mid in self._models.keys()}

    def list_models(self) -> Dict[str, Any]:
        defaults = {"object": "model", "owned_by": "StringSource"}
        data = []
        for mid in self._models.keys():
            data.append(defaults | {"id": mid, "created": self._created.get(mid, int(time.time()))})
        return {"object": "list", "data": data}

    def load_botmark(self, model_id: str) -> Optional[str]:
        return self._models.get(model_id)

class FileSystemSource(BotmarkSource):
    def __init__(self, bot_dir="."):
        super().__init__()
        self.bot_dir = bot_dir

    def list_models(self) -> Dict[str, Any]:
        """Return all available models in bot_dir."""

        botmark_models = []
        if self.bot_dir:
            models_dir = Path(self.bot_dir)
            if models_dir.exists() and models_dir.is_dir():
                for f in models_dir.rglob("*.md"):
                    if f.is_file():
                        try:
                            created = int(f.stat().st_mtime)
                        except Exception:
                            created = int(time.time())

                        # relative Pfad ohne Endung
                        relative_path = f.relative_to(models_dir).with_suffix("")  # entfernt die Endung
                        botmark_models.append( {"id": str(relative_path).replace("\\", "/"), "created": created } )

        defaults = { "object": "model", "owned_by": "FileSystemProvider" }
        return {
            "object": "list",
            "data": [ defaults | m for m in botmark_models ]
        }

    def load_botmark(self, model_id: str):
        """
        Load and return the raw BotMark markdown string for the given model.
        Only `.md` files are supported.
        """
        if not model_id or not self.bot_dir:
            return None

        models_dir = Path(self.bot_dir)
        if not models_dir.exists() or not models_dir.is_dir():
            return None

        model_path = models_dir / (model_id + ".md")
        if model_path.is_file():
            try:
                with open(model_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                print(f"⚠️ Error loading {model_path}: {e}")
                return None

        return None
