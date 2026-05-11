#!/bin/bash
echo "=== Backup DIVEA para Google Drive ==="
echo "Modelos..."
rclone copy ~/divea/models gdrive:DIVEA_backup/models --progress
echo "Dados processados..."
rclone copy ~/divea/data/processed gdrive:DIVEA_backup/processed --progress
echo "=== Backup concluido ==="
