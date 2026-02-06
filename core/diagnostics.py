import threading
import time
import uuid
from dataclasses import dataclass
from typing import Optional, Any, Callable, List


@dataclass
class DiagnosticRecord:
    timestamp: str
    text: str
    context: Optional[Any] = None


class DiagnosticsManager:
    # Lightweight diagnostics manager used by UI to register listeners
    # and obtain snapshots. Heavy emitter/formatting logic removed.

    def __init__(self, capacity: int = 5000, logger=None, only_txrx: bool = False):
        self._lock = threading.RLock()
        self._capacity = max(1, int(capacity))
        self._logger = logger
        self._only_txrx = bool(only_txrx)
        self._records: List[DiagnosticRecord] = []
        self._listeners: dict = {}

    def set_only_txrx(self, value: bool):
        with self._lock:
            self._only_txrx = bool(value)

    def register_listener(
        self,
        name: str,
        callback: Callable[[str, str], None],
        matcher: Optional[Callable[[str, Optional[Any]], bool]] = None,
    ) -> str:
        token = str(uuid.uuid4())
        with self._lock:
            self._listeners[token] = {
                "name": name,
                "callback": callback,
                "matcher": matcher,
            }
        return token

    def unregister_listener(self, token: str):
        with self._lock:
            self._listeners.pop(token, None)

    def clear(self):
        with self._lock:
            self._records.clear()

    def snapshot(self) -> List[DiagnosticRecord]:
        with self._lock:
            return list(self._records)

    def _should_emit(self, text: str, context: Optional[Any] = None) -> bool:
        if not self._only_txrx:
            return True
        t = text or ""
        if ("TX:" in t) or ("RX:" in t):
            return True
        try:
            if isinstance(context, dict):
                dir_val = str(context.get("direction") or "").upper()
                if dir_val in ("TX", "RX"):
                    return True
        except Exception:
            pass
        return False

    def emit(
        self, text: str, context: Optional[Any] = None, timestamp: Optional[str] = None
    ):
        if text is None:
            return
        if not self._should_emit(str(text), context):
            return

        # ✅ 效能優化：只在有 listener（Terminal 視窗開啟）時才記錄訊息
        # 這樣可以避免在沒有開啟 Terminal 時累積大量記錄導致程式變卡
        with self._lock:
            has_listeners = len(self._listeners) > 0
        
        if not has_listeners:
            return  # 沒有開啟的 Terminal 視窗，跳過記錄

        if timestamp is None:
            try:
                now = time.time()
                ms = int((now - int(now)) * 1000)
                timestamp = (
                    time.strftime("%H:%M:%S", time.localtime(now)) + f".{ms:03d}"
                )
            except Exception:
                timestamp = ""

        rec = DiagnosticRecord(timestamp=timestamp, text=str(text), context=context)

        with self._lock:
            self._records.append(rec)
            if len(self._records) > self._capacity:
                self._records = self._records[-self._capacity :]
            listeners = list(self._listeners.values())

        for item in listeners:
            try:
                matcher = item.get("matcher")
                if matcher is not None and not matcher(rec.text, rec.context):
                    continue
                cb = item.get("callback")
                if cb:
                    try:
                        cb(rec.timestamp, rec.text, rec.context)
                    except TypeError:
                        try:
                            cb(rec.timestamp, rec.text)
                        except Exception:
                            pass
                    except Exception:
                        pass
            except Exception:
                try:
                    if self._logger:
                        self._logger.exception("Diagnostics listener failed")
                except Exception:
                    pass

        # emit to configured logger at debug level removed to avoid terminal output

    def stop(self):
        """Stop diagnostics and clear all listeners and records."""
        with self._lock:
            self._listeners.clear()
            self._records.clear()
