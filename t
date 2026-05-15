[0;1;32m●[0m ollama.service - Ollama Service
     Loaded: loaded (]8;;file://valentim-System-Product-Name/etc/systemd/system/ollama.service\/etc/systemd/system/ollama.service]8;;\; [0;1;32menabled[0m; preset: [0;1;32menabled[0m)
     Active: [0;1;32mactive (running)[0m since Mon 2026-05-11 00:20:06 -03; 1h 7min ago
 Invocation: c3331fb8022e4de38096301a5d02c099
   Main PID: 3447 (ollama)
      Tasks: 11[0;38:5:245m (limit: 32101)[0m
     Memory: 187.4M (peak: 295.4M)
        CPU: 389ms
     CGroup: /system.slice/ollama.service
             └─[0;38:5:245m3447 /usr/local/bin/ollama serve[0m

mai 11 00:20:06 valentim-System-Product-Name ollama[3447]: time=2026-05-11T00:20:06.542-03:00 level=INFO source=routes.go:1810 msg="Listening on [::]:11434 (version 0.21.2)"
mai 11 00:20:06 valentim-System-Product-Name ollama[3447]: time=2026-05-11T00:20:06.544-03:00 level=INFO source=runner.go:67 msg="discovering available GPUs..."
mai 11 00:20:06 valentim-System-Product-Name ollama[3447]: time=2026-05-11T00:20:06.546-03:00 level=INFO source=server.go:444 msg="starting runner" cmd="/usr/local/bin/ollama runner --ollama-engine --port 33791"
mai 11 00:20:08 valentim-System-Product-Name ollama[3447]: time=2026-05-11T00:20:08.191-03:00 level=INFO source=server.go:444 msg="starting runner" cmd="/usr/local/bin/ollama runner --ollama-engine --port 35481"
mai 11 00:20:09 valentim-System-Product-Name ollama[3447]: time=2026-05-11T00:20:09.723-03:00 level=INFO source=runner.go:106 msg="experimental Vulkan support disabled.  To enable, set OLLAMA_VULKAN=1"
mai 11 00:20:09 valentim-System-Product-Name ollama[3447]: time=2026-05-11T00:20:09.723-03:00 level=INFO source=types.go:60 msg="inference compute" id=cpu library=cpu compute="" name=cpu description=cpu libdirs=ollama driver="" pci_id="" type="" total="30.1 GiB" available="27.4 GiB"
mai 11 00:20:09 valentim-System-Product-Name ollama[3447]: time=2026-05-11T00:20:09.723-03:00 level=INFO source=routes.go:1860 msg="vram-based default context" total_vram="0 B" default_num_ctx=4096
mai 11 00:21:43 valentim-System-Product-Name ollama[3447]: [GIN] 2026/05/11 - 00:21:43 | 200 |    2.138204ms |      172.17.0.2 | GET      "/api/tags"
mai 11 00:21:43 valentim-System-Product-Name ollama[3447]: [GIN] 2026/05/11 - 00:21:43 | 403 |     299.305µs |     192.168.1.4 | OPTIONS  "/models"
mai 11 00:21:43 valentim-System-Product-Name ollama[3447]: [GIN] 2026/05/11 - 00:21:43 | 200 |      75.409µs |      172.17.0.2 | GET      "/api/version"
