nombre: Script PowerShell
descripcion: función avanzada con parámetros validados, -WhatIf y manejo de errores
lenguaje: powershell
orden: 30
---
Escríbeme un script de PowerShell que: <describe aquí qué debe hacer>
Respeta este andamiaje (CmdletBinding, -WhatIf, try/catch) y explícame cómo probarlo en Windows PowerShell 5.1.

```powershell
<#
.SYNOPSIS
  <qué hace en una línea>
.EXAMPLE
  .\<nombre_del_script>.ps1 -Ruta C:\datos -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path $_ })]
    [string]$Ruta
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

try {
    Write-Verbose "Procesando $Ruta"
    # TODO: lógica principal
    if ($PSCmdlet.ShouldProcess($Ruta, 'Acción')) {
        # cambios reales aquí
    }
}
catch {
    Write-Error "Fallo: $($_.Exception.Message)"
    exit 1
}
```
