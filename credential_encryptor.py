"""
凭据加密工具 — 用 AES-256-GCM 加密敏感配置字段。

用法:
  python credential_encryptor.py init          # 生成主密钥 + 加密当前 .env → .env.enc
  python credential_encryptor.py encrypt       # 用已有主密钥重新加密 .env → .env.enc
  python credential_encryptor.py rotate        # 换新主密钥，重新加密
  python credential_encryptor.py decrypt       # 输出解密后的敏感字段（调试用，慎用）

主密钥存放在项目外的 ~/.qclaw/credentials/ 目录，不进入 git。
"""
import os
import sys
import secrets
import base64
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12
KEY_FILE = Path.home() / ".qclaw" / "credentials" / "earnings-surprise-hunter.key"
PROJECT_DIR = Path(__file__).resolve().parent
ENV_ENC = PROJECT_DIR / ".env.enc"

SENSITIVE_KEYS = {
    "OPENAI_API_KEY",
    "PANDA_DATA_USERNAME",
    "PANDA_DATA_PASSWORD",
}


def _load_env_plain() -> dict[str, str]:
    """从 .env 文件读取原始键值对（不做解析，保留注释行以空白值表示）。"""
    env_file = PROJECT_DIR / ".env"
    if not env_file.exists():
        print(f"ERROR: {env_file} not found", file=sys.stderr)
        sys.exit(1)
    result = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key:
            result[key] = value
    return result


def _generate_key() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def _save_key(key: bytes) -> None:
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_bytes(key)
    # Windows: 限制只允许当前用户读取
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(str(KEY_FILE), 2)  # FILE_ATTRIBUTE_HIDDEN


def _load_key() -> bytes:
    if not KEY_FILE.exists():
        print(f"ERROR: master key not found at {KEY_FILE}", file=sys.stderr)
        print("  Run: python credential_encryptor.py init", file=sys.stderr)
        sys.exit(1)
    return KEY_FILE.read_bytes()


def encrypt():
    """加密 .env 中的敏感字段，写入 .env.enc"""
    key = _load_key()
    aes = AESGCM(key)
    env = _load_env_plain()

    # 只处理敏感键
    sensitive = {k: v for k, v in env.items() if k in SENSITIVE_KEYS and v}
    if not sensitive:
        print("No sensitive fields with values found in .env", file=sys.stderr)
        sys.exit(1)

    for k, v in sensitive.items():
        nonce = os.urandom(NONCE_BYTES)
        ciphertext = aes.encrypt(nonce, v.encode("utf-8"), None)
        sensitive[k] = base64.b64encode(nonce + ciphertext).decode("ascii")

    # 也保留非敏感字段（BASE_URL, MODEL 等）
    non_sensitive = {k: v for k, v in env.items() if k not in SENSITIVE_KEYS and v}
    payload = {**non_sensitive, **sensitive}
    lines = [f"{k}={v}" for k, v in payload.items()]
    ENV_ENC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Encrypted {len(sensitive)} field(s) → {ENV_ENC}")


def decrypt_into_dict() -> dict[str, str]:
    """解密 .env.enc，返回完整的 env 字典。"""
    if not ENV_ENC.exists():
        return {}
    key = _load_key()
    aes = AESGCM(key)
    result = {}
    for line in ENV_ENC.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if k in SENSITIVE_KEYS and v:
            try:
                raw = base64.b64decode(v.encode("ascii"))
                nonce, ciphertext = raw[:NONCE_BYTES], raw[NONCE_BYTES:]
                v = aes.decrypt(nonce, ciphertext, None).decode("utf-8")
            except Exception:
                raise ValueError(f"Failed to decrypt {k} — master key may be stale")
        result[k] = v
    return result


def cmd_decrypt():
    """命令行: 输出解密后的完整 .env.enc（调试用）。"""
    data = decrypt_into_dict()
    for k, v in data.items():
        print(f"{k}={v}")


def cmd_init():
    """生成主密钥 + 首次加密。"""
    # 检查是否已有 .env.enc 存在
    already = ENV_ENC.exists()

    if not already:
        raw = _load_env_plain()
        has_sensitive = any(raw.get(k) for k in SENSITIVE_KEYS)
        if not has_sensitive:
            print("No sensitive values in .env — fill them first, then re-run.", file=sys.stderr)
            sys.exit(1)

    key = _generate_key()
    _save_key(key)
    print(f"Master key → {KEY_FILE} (hidden)")

    encrypt()
    if already:
        print(".env.enc re-encrypted with new key.")
    else:
        print("Done. Now clear sensitive values from .env and keep only non-sensitive config.")
        print("Or delete .env entirely — the script reads .env.enc + non-sensitive from .env.")


def cmd_rotate():
    """更换主密钥，重新加密。"""
    if not KEY_FILE.exists():
        print("No existing key — use 'init' instead.", file=sys.stderr)
        sys.exit(1)
    key = _generate_key()
    _save_key(key)
    print(f"New master key → {KEY_FILE} (hidden)")
    encrypt()
    print("Credentials re-encrypted with new key.")


if __name__ == "__main__":
    cmds = {"init": cmd_init, "encrypt": encrypt, "rotate": cmd_rotate, "decrypt": cmd_decrypt}
    if len(sys.argv) != 2 or sys.argv[1] not in cmds:
        print(f"Usage: python {Path(__file__).name} <init|encrypt|rotate|decrypt>", file=sys.stderr)
        sys.exit(1)
    cmds[sys.argv[1]]()
