@echo off
REM ============================================================================
REM  02CartoLab Practical Guide — screenshot generator
REM
REM  Runs every documented CartoLab capability in a real QGIS runtime against
REM  real urban data and writes publication-grade panel composites to
REM  docs\PRACTICAL_GUIDE\screenshots\ plus manifest\screenshots.json.
REM
REM  Usage:
REM    run_practical_guide.bat                 REM everything
REM    run_practical_guide.bat --all           REM everything
REM    run_practical_guide.bat --module bivariate
REM    run_practical_guide.bat --module layout_templates --module gui_dashboard
REM
REM  Then rebuild the guide:
REM    python build_guide.py
REM    python optimize_images.py
REM ============================================================================
setlocal
cd /d "%~dp0"

set "QGIS_PY=C:\OSGeo4W\bin\python-qgis-ltr.bat"
if not exist "%QGIS_PY%" set "QGIS_PY=C:\OSGeo4W\bin\python-qgis.bat"
if not exist "%QGIS_PY%" (
    echo [ERROR] No QGIS Python found at C:\OSGeo4W\bin\python-qgis-ltr.bat
    echo         Install QGIS via OSGeo4W, or set QGIS_PY manually.
    exit /b 1
)

if "%~1"=="" (
    echo Running every module ^(this takes a few minutes^)...
    "%QGIS_PY%" practical_guide_runner.py --all
) else (
    "%QGIS_PY%" practical_guide_runner.py %*
)

if errorlevel 1 (
    echo [ERROR] Screenshot generation failed.
    exit /b 1
)

echo.
echo Rebuilding the guide...
where python >nul 2>nul && python build_guide.py || py -3 build_guide.py
where python >nul 2>nul && python optimize_images.py || py -3 optimize_images.py

echo.
echo Done. Open practical_guide.html
endlocal
