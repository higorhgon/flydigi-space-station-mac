#!/usr/bin/env python3
"""Ask Flydigi's update server for Apex 3 (`k1`) firmware, download what it offers and check the image header.

Same request Space Station 4 makes for the Apex 4 (docs/spacestation4-analysis.md §6), with the device code and
ids switched to the Apex 3 family and every chip reported at a dummy version so the server offers whatever it has.
Header checks follow docs/firmware-update.md §4 (Telink: KNLT mark, size at 0x18, CRC32 without final inversion).
Nothing here talks to the controller. Standard library only.

Usage:
  scripts/k1-firmware-probe.py                      # ids 29 (One Piece), 24 (Apex 3), 26 (AeroSpace)
  scripts/k1-firmware-probe.py --ids 29 --out fw-k1
  scripts/k1-firmware-probe.py --check fw-k1/some.bin   # only validate a local file
"""

import argparse
import hashlib
import json
import pathlib
import struct
import sys
import urllib.parse
import urllib.request
import zlib

API = "https://api.flydigi.com/pc/Update/firmware"
# Ids from FlydigiKit's DeviceCatalog: 29 One Piece, 24 Apex 3, 26 AeroSpace.
DEFAULT_IDS = [29, 24, 26]
DEFAULT_APP_VERSIONS = ["4.2.2.3", "4.1.2.0"]
CHIPS = ["main_chip", "dongle_chip", "screen_chip", "si_chip", "trigger_chip", "rf_chip"]
DUMMY = "0.0.0.1"


def query(device_code, device_id, app_version):
    body = {"device_code": device_code, "device_id": device_id, "app_version": app_version}
    body.update({c: DUMMY for c in CHIPS})
    req = urllib.request.Request(API, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "appversion": app_version})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def trusted(url):
    u = urllib.parse.urlparse(url)
    h = (u.hostname or "").lower()
    return u.scheme == "https" and (h == "flydigi.com" or h.endswith(".flydigi.com"))


def download(url, out_dir):
    name = pathlib.PurePosixPath(urllib.parse.urlparse(url).path).name or "firmware.bin"
    dest = out_dir / name
    if dest.exists():
        print(f"    já baixado: {dest}")
        return dest
    req = urllib.request.Request(url, headers={"appversion": DEFAULT_APP_VERSIONS[0]})
    with urllib.request.urlopen(req, timeout=60) as r:
        dest.write_bytes(r.read())
    print(f"    salvo em {dest}")
    return dest


def check(path):
    data = pathlib.Path(path).read_bytes()
    print(f"    {len(data)} B, sha256 {hashlib.sha256(data).hexdigest()}")
    print(f"    primeiros 32 B: {data[:32].hex(' ')}")
    if len(data) < 0x24:
        print("    pequeno demais para uma imagem Telink")
        return False
    version, = struct.unpack_from("<I", data, 0x02)
    size, = struct.unpack_from("<I", data, 0x18)
    mark = data[0x08:0x0C]
    print(f"    campo de versão @0x02: 0x{version:08x}")
    print(f"    marca @0x08: {mark!r} {'(KNLT, Telink)' if mark == b'KNLT' else '(não é KNLT)'}")
    if not 0x20 <= size <= len(data):
        print(f"    campo de tamanho @0x18 = {size} não cabe no arquivo — provavelmente não é o formato Telink do Apex 4")
        return False
    stored, = struct.unpack_from("<I", data, size - 4)
    computed = zlib.crc32(data[:size - 4]) ^ 0xFFFFFFFF  # registro IEEE sem a inversão final
    ok = mark == b"KNLT" and stored == computed and stored not in (0, 0xFFFFFFFF)
    print(f"    tamanho @0x18: {size}" + (f" (+{len(data) - size} B depois)" if size != len(data) else ""))
    print(f"    CRC32 no arquivo {stored:08x}, calculado {computed:08x} → {'confere' if stored == computed else 'NÃO confere'}")
    print(f"    {'imagem Telink válida' if ok else 'imagem não validou como Telink'}")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ids", type=int, nargs="+", default=DEFAULT_IDS, help="device ids (padrão: 29 24 26)")
    ap.add_argument("--code", default="k1", help="device_code (padrão: k1)")
    ap.add_argument("--app-version", nargs="+", default=DEFAULT_APP_VERSIONS, help="versões do Space Station a simular")
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("fw-k1"), help="pasta de saída (padrão: fw-k1)")
    ap.add_argument("--no-download", action="store_true", help="só mostra as respostas")
    ap.add_argument("--check", type=pathlib.Path, help="só valida um .bin local")
    a = ap.parse_args()

    if a.check:
        print(a.check)
        return 0 if check(a.check) else 1

    a.out.mkdir(parents=True, exist_ok=True)
    found = {}
    answered = 0
    for device_id in a.ids:
        for app_version in a.app_version:
            print(f"== {a.code} id {device_id}, app {app_version}")
            try:
                reply = query(a.code, device_id, app_version)
            except Exception as e:  # rede, HTTP, JSON
                print(f"    erro: {e}")
                continue
            answered += 1
            (a.out / f"reply-{a.code}-{device_id}-{app_version}.json").write_text(json.dumps(reply, ensure_ascii=False, indent=2))
            chips = (reply.get("data") or {}).get("chip_list") or {}
            if not isinstance(chips, dict) or not chips:
                print(f"    nada oferecido (code {reply.get('code')}, {reply.get('message') or reply.get('msg') or 'sem mensagem'})")
                continue
            for chip, info in chips.items():
                url = info.get("url", "")
                print(f"    {chip}: versão {info.get('version')}  min_app {info.get('min_app_version')}")
                print(f"    url: {url}")
                if info.get("info"):
                    print("    notas: " + info["info"].replace("\n", " / "))
                found.setdefault(url, (device_id, chip))

    if not answered:
        print("\nNenhuma consulta teve resposta (rede/proxy?).")
        return 2
    if not found:
        print("\nO servidor não ofereceu firmware para nenhum id. Veja as respostas JSON em", a.out)
        return 1
    if a.no_download:
        return 0
    print()
    for url, (device_id, chip) in found.items():
        print(f"== baixando {chip} (id {device_id})")
        if not trusted(url):
            print(f"    pulado: host fora de *.flydigi.com ({url})")
            continue
        try:
            check(download(url, a.out))
        except Exception as e:
            print(f"    erro: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
