# -*- coding: utf-8 -*-
"""
Encrypt the GitHub token with a password so the admin page only needs the password.

  python _tools/set_admin_password.py <github_token> <password>

Writes _tools/admin_secret.json (committed; deployed next to admin.html).
PBKDF2-HMAC-SHA256 (600k iterations) -> AES-256-GCM. A longer password = much better protection.
"""
import base64
import json
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITER = 600_000
OUT = Path(__file__).resolve().parent / "admin_secret.json"


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    token, password = sys.argv[1].strip(), sys.argv[2]
    if len(password) < 3:
        sys.exit("password too short")
    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(password.encode("utf-8"))
    ct = AESGCM(key).encrypt(iv, token.encode("utf-8"), None)
    b64 = lambda b: base64.b64encode(b).decode()
    OUT.write_text(json.dumps({"v": 1, "kdf": "PBKDF2-SHA256", "iter": ITER, "salt": b64(salt), "iv": b64(iv), "ct": b64(ct)}, indent=1), encoding="utf-8")
    print(f"written {OUT}  (password length {len(password)})")
    if len(password) < 8:
        print("WARNING: a password under 8 characters can be brute-forced offline; use a repo-scoped fine-grained token.")


if __name__ == "__main__":
    main()
