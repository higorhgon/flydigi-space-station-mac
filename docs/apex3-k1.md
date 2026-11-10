# Apex 3 (`k1`) — estado do reconhecimento

Controle: Apex 3 edição One Piece. Objetivo: obter o firmware (talvez traduzir a tela) e, no Linux, uma ponte
uhid DualSense virtual → gatilhos de força. Tudo abaixo foi medido no Linux (Arch/Omarchy) em 2026-10-31.

## Regras
- **Nunca gravar firmware** no controle.
- O único comando já enviado ao Apex 3 é `05 EC` (consulta de info). Qualquer outra escrita — inclusive consultas
  — só com pedido explícito do dono do controle.
- Se o Space Station oferecer atualização, **não aceitar**; só registrar a URL.

## USB/HID (modo DInput, `04b4:2412`, bcdDevice 5.00, strings "Flydigi APEX3")
| Interface | Uso |
|---|---|
| 0 | gamepad, sem report id |
| 1 | mouse boot, report id 2 |
| 2 | vendor `0xFFA0`: in id 4, out id 5, 31 B + id |
| 3 | Consumer Control, report id 3 |

- Não existe a interface OTA `0xFFEF` do Apex 4; o caminho de atualização do Apex 3 é desconhecido.
- `0xFFA0` transmite `04 FE …` a ~267 Hz; sticks nos mesmos offsets do Apex 4 (`protocol.md` §9).

## `05 EC` (device info) — verificado
Enviado uma vez, 32 B (`05 EC` + zeros) na `0xFFA0`. Resposta em 9 ms, mesmo layout do Apex 4 em DInput
(`r[15] = 0xEC`):

`04 ff f0 1d 00 <mac 4 B> 52 64 04 01 01 02 ec 2f …`

| Campo | Valor |
|---|---|
| device id `r[3]` | 29 (One Piece) |
| firmware `r[9..10]` | **6.4.5.2** |
| bateria `r[11]` | 4 |
| cpu `r[12]` | 1 — significado desconhecido (se for o enum `ChipType` do SS4, seria WCH; não confirmado) |
| conexão `r[13]` | 1 (cabo) |
| motion `r[14]` | 2 |

O controle continuou enumerado e funcionando.

## Servidor de firmware
`POST https://api.flydigi.com/pc/Update/firmware` (ver `spacestation4-analysis.md` §6, `scripts/k1-firmware-probe.py`):
- 66 consultas para o Apex 3 → todas `{"code":1,"message":"No firmware information found for the device"}`.
  Variações: códigos `k1 K1 apex3 APEX3 k1p k3`, ids 29/24/26, app 4.2.2.3/4.1.2.0/3.3.1.0, `main_chip` dummy,
  6.4.5.2, 6.4.5.0 e 6.4.0.0, com e sem `screen_chip`/`trigger_chip`.
- Controle positivo: `k2`/84/`6.8.3.0` continua recebendo 6.8.3.7 — o endpoint funciona.
- Conclusão provisória: ou o Apex 3 usa outro endpoint/código/formato, ou o servidor não tem imagem para ele.

## Próximo passo: Windows nativo
1. Instalar o Space Station oficial (o que suporta o Apex 3; anotar a versão).
2. **Rede:** Fiddler Classic com descriptografia HTTPS ativa (o serviço .NET usa o proxy do sistema).
   Abrir o SS, conectar o controle e pedir "verificar atualização". Salvar a sessão (`.saz`).
   Procurar: endpoint, `device_code`, `device_id`, nomes dos chips e a resposta (URL de `.bin`, se houver).
3. **USB:** Wireshark com USBPcap no root hub do controle, ligado *antes* de abrir o SS. Salvar `.pcapng`.
   Interessa: comandos que o SS envia ao Apex 3 (consulta de versões por chip, troca de modo, etc.).
4. Se aparecer URL de firmware: baixar só o arquivo e validar com `scripts/k1-firmware-probe.py --check`.
5. Se nada aparecer: análise estática do Space Station (ramo `k1`), como foi feito com o SS4.
6. Último recurso: abrir o controle e fotografar a placa para identificar os chips antes de qualquer leitura
   por SWire/SPI/WCH-Link.
