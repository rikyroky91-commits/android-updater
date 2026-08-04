# OnePlus Anti-Rollback (ARB) Checker

<!--
Estratto REGISTRATO dal README di github.com/Bartixxx32/OnePlus-antirollchecker
il 2026-08-04. Il README e' generato a macchina da generate_readme.py, quindi
il formato e' stabile. Contenuti scelti per coprire i casi veri:
  - OnePlus 13: cinque regioni, codici diversi per regione, tabella storica
  - OnePlus Nord CE 4: una sola regione (CPH2613)
  - OnePlus 9RT: ARB "?" e stato "Undetectable"
  - OnePlus 12R: build vecchio stile CPH2611_11_A.65
  - Oppo Reno10 Pro: OPPO, non OnePlus, con suffissi regione nel codice
  - Oppo Find N5: la Cina ha codice modello diverso dalla build
Se il formato cambia, il modo giusto di aggiornare questo file e' ricatturarlo.
-->

Automated ARB (Anti-Rollback) index tracker for OnePlus devices.

## 📊 Current Status

### OnePlus 13

| Region | Model | Firmware Version | ARB Index | OEM Version | Last Checked | Safe |
| --- | --- | --- | --- | --- | --- | --- |
| Global | CPH2653 | CPH2653_16.0.5.703(EX01)<br>**MD5** `bd7bffda1812ac8732704fb38a0fc1c8` | **1** | Major: 3, Minor: 0 | 2026-05-17 | ❌ Protected |
| Europe | CPH2653 | CPH2653_16.0.5.703(EX01)<br>**MD5** `5eb404fefe6c48fd4996f25bda682034` | **1** | Major: 3, Minor: 0 | 2026-05-17 | ❌ Protected |
| India | CPH2649 | CPH2649_16.0.7.201(EX01)<br>**MD5** `5d9c6f88d64fff22d6f6ca659e4dfc1f` | **1** | Major: 3, Minor: 0 | 2026-05-17 | ❌ Protected |
| North America | CPH2655 | CPH2655_15.0.0.832(EX01)<br>**MD5** `7d0ce94be24263393454ae140889a523` | **0** | Major: 3, Minor: 0 | 2026-05-17 | ✅ Safe |
| China | PJZ110 | PJZ110_16.0.7.201(CN01)<br>**MD5** `afc5eb1ec721995687d4f27833d0f8e0` | **1** | Major: 3, Minor: 0 | 2026-05-17 | ❌ Protected |

<details>
<summary><b>📜 India History (click to expand)</b></summary>

| Firmware Version | ARB | OEM Version | Last Seen | Safe |
| --- | --- | --- | --- | --- |
| CPH2649_16.0.5.703(EX01)<br>**MD5** `0efa2594bf5466c84bafd4e19073d95e` | 1 | Major: 3, Minor: 0 | 2026-05-14 | ❌ Protected |
| CPH2649_16.0.5.701(EX01)<br>**MD5** `6998133c921d754bf06e693455aabcdc` | 1 | Major: 3, Minor: 0 | 2026-04-13 | ❌ Protected |
| CPH2649_15.0.0.860(EX01)<br>**MD5** `7792bdabc5d756298ab6891d6fa4711c` | 0 | Major: 3, Minor: 0 | 2026-03-10 | ✅ Safe |

</details>

---

### OnePlus Nord CE 4

| Region | Model | Firmware Version | ARB Index | OEM Version | Last Checked | Safe |
| --- | --- | --- | --- | --- | --- | --- |
| India | CPH2613 | CPH2613_16.0.5.700(EX01)<br>**MD5** `f08b3046c8ed7b7a6baf1e72d16d815f` | **0** | Major: 2, Minor: 0 | 2026-05-17 | ✅ Safe |

<details>
<summary><b>📜 India History (click to expand)</b></summary>

| Firmware Version | ARB | OEM Version | Last Seen | Safe |
| --- | --- | --- | --- | --- |
| CPH2613_16.0.3.500(EX01)<br>**MD5** `3990e7a5b3eb6dd87b82ab4ee9efebbd` | 0 | Major: 2, Minor: 0 | 2026-03-31 | ✅ Safe |

</details>

---

### OnePlus 9RT

| Region | Model | Firmware Version | ARB Index | OEM Version | Last Checked | Safe |
| --- | --- | --- | --- | --- | --- | --- |
| India | MT2111 | MT2111_14.0.0.2702(EX01)<br>**MD5** `ce87f568d2c236229f628f95bb82a08a` | **?** | Major: 0, Minor: 120 | 2026-05-17 | ⚠️ Undetectable ARB |

---

### OnePlus 12R

| Region | Model | Firmware Version | ARB Index | OEM Version | Last Checked | Safe |
| --- | --- | --- | --- | --- | --- | --- |
| Global | CPH2609 | CPH2609_16.0.5.701(EX01)<br>**MD5** `21b571911450b6b291bf4be623a0973b` | **0** | Major: 2, Minor: 0 | 2026-05-17 | ✅ Safe |
| India | CPH2585 | CPH2585_16.0.5.702(EX01)<br>**MD5** `bf4e0cccac0d0a2298689a1e5ce22dcf` | **0** | Major: 2, Minor: 0 | 2026-05-17 | ✅ Safe |
| North America | CPH2611 | CPH2611_11_A.65<br>**MD5** `a16a2f0dbbd5eeaff10041299f4d1508` | **0** | Major: 2, Minor: 0 | 2026-05-17 | ✅ Safe |

---

### Oppo Reno10 Pro

| Region | Model | Firmware Version | ARB Index | OEM Version | Last Checked | Safe |
| --- | --- | --- | --- | --- | --- | --- |
| Singapore | CPH2525SG | CPH2525_15.0.0.1603(EX01)<br>**MD5** `308573b1553dc7381448f4a4a669b42c` | **0** | Major: 0, Minor: 120 | 2026-05-17 | ✅ Safe |
| Europe | CPH2525EEA | CPH2525_15.0.0.1603(EX01)<br>**MD5** `128650aa4175ac0e3c4cda9f3ae9eb25` | **0** | Major: 0, Minor: 120 | 2026-04-23 | ✅ Safe |
| India | CPH2525IN | CPH2525_13.1.1.147(EX01)<br>**MD5** `abb2a1ef3450621de3073f48d5215b19` | **0** | Major: 0, Minor: 120 | 2026-05-17 | ✅ Safe |

---

### Oppo Find N5

| Region | Model | Firmware Version | ARB Index | OEM Version | Last Checked | Safe |
| --- | --- | --- | --- | --- | --- | --- |
| Singapore | CPH2671 | CPH2671_16.0.5.700(EX01)<br>**MD5** `84b434d3337990b381cb6de3898f7c8e` | **0** | Major: 3, Minor: 0 | 2026-05-17 | ✅ Safe |
| China | PKV110 | PKH110_16.0.3.500(CN01)<br>**MD5** `0f0d5e5ca45e64af32b99f7401d65a12` | **0** | Major: 3, Minor: 0 | 2026-05-17 | ✅ Safe |

---

## 🤖 On-Demand ARB Checker

You can check the ARB index of any OnePlus Ozip/Zip URL manually using our automated workflow.

*Last updated: 2026-05-17 04:01 UTC*
