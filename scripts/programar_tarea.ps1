<#
Registra la rutina diaria (Sabueso + Centinela) en el Programador de
tareas de Windows. Córrelo UNA vez, desde la raíz del proyecto:

    powershell -ExecutionPolicy Bypass -File scripts\programar_tarea.ps1
    powershell -ExecutionPolicy Bypass -File scripts\programar_tarea.ps1 -Hora 09:30

Para quitarla:

    Unregister-ScheduledTask -TaskName "Job-Intelligence rutina diaria" -Confirm:$false

Corre solo con tu sesión iniciada (así puede mostrarte la notificación)
y, si el PC estaba apagado a esa hora, se ejecuta al encenderlo.
#>
param(
    [string]$Hora = "08:00"
)

$raiz = Split-Path -Parent $PSScriptRoot
$python = Join-Path $raiz "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "No encontré $python. Crea el venv e instala requirements.txt primero."
}

$accion = New-ScheduledTaskAction -Execute $python -Argument "-m scripts.rutina_diaria" -WorkingDirectory $raiz
$disparador = New-ScheduledTaskTrigger -Daily -At $Hora
$opciones = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask -TaskName "Job-Intelligence rutina diaria" `
    -Description "Sabueso busca ofertas nuevas y Centinela arma el resumen diario." `
    -Action $accion -Trigger $disparador -Settings $opciones -Force | Out-Null

Write-Host "Listo: la rutina correrá todos los días a las $Hora."
Write-Host "Probarla ahora: Start-ScheduledTask -TaskName 'Job-Intelligence rutina diaria'"
