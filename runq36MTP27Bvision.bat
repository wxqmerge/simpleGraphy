cd /d %~dp0
set "name=%~n0"
title %name%
if exist %name%.log.5 del %name%.log.5
if exist %name%.log.4 ren %name%.log.4 %name%.log.5
if exist %name%.log.3 ren %name%.log.3 %name%.log.4
if exist %name%.log.2 ren %name%.log.2 %name%.log.3
if exist %name%.log.1 ren %name%.log.1 %name%.log.2
if exist %name%.log ren %name%.log %name%.log.1

.\llama-server --model "D:\models\Qwen3.6-27B-UD-Q5_K_XL.gguf" --mmproj "D:\models\mmproj-BF16-27B.gguf" --alias "Qwen3.6-27B Vision" --temp 0.3 --top-p 0.9 -fit on --top-k 20 --min-p 0.00 --jinja --host 0.0.0.0 --threads 24 --api-key sk-123 --log-file %name%.log --presence_penalty 0.0 --spec-type draft-mtp --spec-draft-n-max 2 --image-min-tokens 1024 --ctx-size 32768 --n-predict 512 -np 1 --flash-attn on

pause