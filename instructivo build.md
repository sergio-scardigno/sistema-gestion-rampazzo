# Instructivo Build y Release (versiones futuras)

Este instructivo sirve para sacar una nueva version, subirla a Git y ejecutar build local + multibuild sin que salga una version vieja.

## Objetivo

- Subir al remoto **el codigo real** de la nueva version.
- Actualizar `APP_VERSION`.
- Ejecutar release local + multiplataforma.
- Obtener los ZIP finales por plataforma.

## Requisitos previos

- Estar en la raiz del repo:

```powershell
cd "C:\Users\Sergio\proyectos\sistema-gestion-rampazzo"
```

- Tener `gh` autenticado:

```powershell
gh auth status
```

- Tener rama correcta (ejemplo):

```powershell
git branch --show-current
```

## Regla clave (evitar build "viejo")

Antes de correr release, **primero** hay que commitear/pushear todos los cambios funcionales (dashboard, spec, etc.).  
Si solo se sube `config.py`, GitHub Actions compila codigo viejo.

---

## Flujo recomendado completo

Reemplazar `1.7.5` por la version nueva (ejemplo: `1.7.6`).

### 1) Ver estado local

```powershell
git status --short
```

### 2) Commit y push del codigo funcional (no version)

Ejemplo (ajusta archivos segun tu cambio real):

```powershell
git add "views/dashboard_view.py" "SistemaRampazzo.spec"
git commit --author "Sergio Scardigno <sergioscardigno82@gmail.com>" -m "actualiza funcionalidades previas al release"
git push origin HEAD
```

Validar:

```powershell
git status --short
git log --oneline -3
```

### 3) Actualizar version en `config.py`

```powershell
(Get-Content "config.py" -Raw) -replace 'APP_VERSION\s*=\s*"[^"]+"', 'APP_VERSION = "1.7.5"' | Set-Content "config.py" -Encoding UTF8
```

Verificar:

```powershell
Select-String -Path "config.py" -Pattern 'APP_VERSION\s*='
```

### 4) Commit y push de version

```powershell
git add "config.py"
git commit --author "Sergio Scardigno <sergioscardigno82@gmail.com>" -m "v1.7.5 - release multiplataforma"
git push origin HEAD
```

Validar:

```powershell
git log --oneline -5
```

### 5) Ejecutar release completo (local + multibuild)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\release_multiplataforma.ps1" -Version "1.7.5"
```

Este script hace:

- build local (`build.py`)
- workflow multiplataforma en GitHub Actions
- descarga y organiza artifacts

---

## Verificacion final de artifacts

```powershell
ls "dist_out\win-1.7.5"
ls "dist_out\linux-1.7.5"
ls "dist_out\mac-1.7.5"
```

Esperado:

- `SistemaRampazzo-win-1.7.5.zip`
- `SistemaRampazzo-linux-1.7.5.zip`
- `SistemaRampazzo-mac-1.7.5.zip`

---

## Comandos utiles (si algo falla)

### A) Confirmar que la version del repo remoto es la correcta

```powershell
git show --name-only --oneline -1
```

Y validar `config.py`:

```powershell
Select-String -Path "config.py" -Pattern 'APP_VERSION\s*='
```

### B) Si el release queda colgado en descarga de artifacts

1. Ver run reciente:

```powershell
gh run list --workflow "build.yml" --limit 5
```

2. Descargar artifacts manualmente del run correcto:

```powershell
gh run download <RUN_ID> -R sergio-scardigno/sistema-gestion-rampazzo -D "dist_out\_tmp_download_1.7.5"
```

3. Copiar artifacts a carpetas finales:

```powershell
Copy-Item -Force "dist_out\_tmp_download_1.7.5\SistemaRampazzo.zip" "dist_out\win-1.7.5\SistemaRampazzo-win-1.7.5.zip"
Copy-Item -Force "dist_out\_tmp_download_1.7.5\SistemaRampazzo-Linux\SistemaRampazzo.zip" "dist_out\linux-1.7.5\SistemaRampazzo-linux-1.7.5.zip"
Copy-Item -Force "dist_out\_tmp_download_1.7.5\SistemaRampazzo-macOS\SistemaRampazzo.zip" "dist_out\mac-1.7.5\SistemaRampazzo-mac-1.7.5.zip"
```

---

## Checklist rapido antes de cada release

- [ ] `git status --short` revisado
- [ ] Cambios funcionales commiteados y pusheados
- [ ] `APP_VERSION` actualizada
- [ ] Commit de version hecho y pusheado
- [ ] `release_multiplataforma.ps1` ejecutado
- [ ] ZIPs finalizados en `dist_out/win-*`, `dist_out/linux-*`, `dist_out/mac-*`

