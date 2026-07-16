@echo off
setlocal EnableExtensions

rem Windows 一键运行：语义特征小提琴图、箱线图和散点图
set "PROJECT_DIR=E:\Barrel_SEM_Z1_Z4_New"
set "DATA_DIR=E:\Barrel_SEM_Z1_Z4_New\05_tables"
set "OUTPUT_DIR=E:\Barrel_SEM_Z1_Z4_New\06_figures\semantic_feature_violin"
set "SCRIPT_PATH=E:\Barrel_SEM_Z1_Z4_New\10_code\make_semantic_feature_violin_box_scatter.py"

rem 优先使用 Windows Python Launcher；没有时退回 PATH 中的 python。
where py >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3"
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [错误] 未找到 Python。请安装 Python 3，并确保 py 或 python 已加入 PATH。
        pause
        exit /b 1
    )
    set "PYTHON_EXE=python"
    set "PYTHON_ARGS="
)

"%PYTHON_EXE%" %PYTHON_ARGS% --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Python 无法正常启动，请检查 Python 3 安装。
    pause
    exit /b 1
)

if not exist "%SCRIPT_PATH%" (
    echo [错误] 未找到绘图脚本："%SCRIPT_PATH%"
    pause
    exit /b 1
)

if not exist "%DATA_DIR%" (
    echo [错误] 未找到数据目录："%DATA_DIR%"
    pause
    exit /b 1
)

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
cd /d "%PROJECT_DIR%"
echo [信息] 数据目录："%DATA_DIR%"
echo [信息] 输出目录："%OUTPUT_DIR%"
echo [信息] 正在运行绘图脚本，请等待……
"%PYTHON_EXE%" %PYTHON_ARGS% "%SCRIPT_PATH%" --data-dir "%DATA_DIR%" --output-dir "%OUTPUT_DIR%"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo [错误] 脚本运行失败，退出代码：%EXIT_CODE%
) else (
    echo [完成] 图形、统计结果和日志已写入："%OUTPUT_DIR%"
)
pause
exit /b %EXIT_CODE%
