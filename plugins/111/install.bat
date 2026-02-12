@echo off
chcp 65001 >nul
title Claude Code Skill 安装程序

:: 技能信息（由服务器动态替换）
set SKILL_NAME=auditing-python-security-1.0.2
set SKILL_VERSION=1.0.2
set SKILL_DIR=auditing-python-security-1.0.2

:: 颜色定义
set GREEN=[92m
set YELLOW=[93m
set RED=[91m
set CYAN=[96m
set NC=[0m

echo.
echo %CYAN%========================================%NC%
echo %CYAN%  Claude Code Skill 一键安装程序%NC%
echo %CYAN%========================================%NC%
echo.
echo 技能名称: %SKILL_NAME%
echo 版本: %SKILL_VERSION%
echo.

:: ====================
:: 步骤1: 检测 CLAUDE_SKILLS_PATH
:: ====================
if defined CLAUDE_SKILLS_PATH (
    if exist "%CLAUDE_SKILLS_PATH%" (
        set SKILLS_DIR=%CLAUDE_SKILLS_PATH%
        echo %GREEN%[OK]%NC% 从环境变量 CLAUDE_SKILLS_PATH 检测到 Skills 目录
        echo     %SKILLS_DIR%
        goto :verify_and_install
    ) else (
        echo %YELLOW%[WARN]%NC% 环境变量 CLAUDE_SKILLS_PATH 指向的路径不存在:
        echo     %CLAUDE_SKILLS_PATH%
    )
)

:: ====================
:: 步骤2: 检测默认路径
:: ====================
set DEFAULT_PATH=%USERPROFILE%\.claude\skills
if exist "%DEFAULT_PATH%" (
    set SKILLS_DIR=%DEFAULT_PATH%
    echo %GREEN%[OK]%NC% 从默认位置检测到 Skills 目录
    echo     %SKILLS_DIR%
    goto :verify_and_install
)

:: ====================
:: 步骤3: 交互式输入
:: ====================
echo.
echo %YELLOW%[WARN]%NC% 未自动检测到 Claude Code Skills 目录
echo.
echo 常见位置:
echo   - Windows: %%USERPROFILE%%\.claude\skills\
echo   - 自定义: 请指定您的 Claude Code 配置目录下的 skills 文件夹
echo.

:input_loop
set /p SKILLS_DIR="请输入 Skills 目录完整路径: "

:: 去除首尾空格
for /f "tokens=*" %%a in ("%SKILLS_DIR%") do set SKILLS_DIR=%%a

:: 检查路径是否存在
if not exist "%SKILLS_DIR%" (
    echo %RED%[ERR]%NC% 路径不存在: %SKILLS_DIR%
    choice /c YN /n /m "是否创建此目录? (Y/N) "
    if errorlevel 2 goto :input_loop
    if errorlevel 1 (
        mkdir "%SKILLS_DIR%" 2>nul
        if errorlevel 1 (
            echo %RED%[ERR]%NC% 创建目录失败，请检查权限
            goto :input_loop
        )
        echo %GREEN%[OK]%NC% 已创建目录: %SKILLS_DIR%
    )
)

:: 验证目录结构
if not exist "%SKILLS_DIR%\..\.." (
    echo %YELLOW%[WARN]%NC% 警告: 该路径可能不是标准的 Skills 目录
    choice /c YN /n /m "是否继续使用此路径? (Y/N) "
    if errorlevel 2 goto :input_loop
)

:: ====================
:: 验证并安装
:: ====================
:verify_and_install
echo.
echo %CYAN%目标安装路径:%NC% %SKILLS_DIR%
echo.

:: 检查目标是否已存在
set TARGET_PATH=%SKILLS_DIR%\%SKILL_DIR%
if exist "%TARGET_PATH%" (
    echo %YELLOW%[WARN]%NC% 检测到同名技能已存在: %SKILL_DIR%
    echo.
    echo 请选择操作:
    echo   [1] 覆盖安装 (删除旧版本)
    echo   [2] 跳过安装 (保留旧版本)
    echo   [3] 备份并安装 (旧版本重命名为 .backup)
    echo.

    choice /c 123 /n /m "请选择 (1/2/3): "

    if errorlevel 3 (
        :: 备份
        set BACKUP_NAME=%SKILL_DIR%.backup.%date:~0,4%%date:~5,2%%date:~8,2%-%time:~0,2%%time:~3,2%%time:~6,2%
        set BACKUP_NAME=!BACKUP_NAME: =0!
        rename "%TARGET_PATH%" "!BACKUP_NAME!" >nul 2>&1
        if errorlevel 1 (
            echo %RED%[ERR]%NC% 备份失败，请检查权限
            goto :error_exit
        )
        echo %GREEN%[OK]%NC% 已备份旧版本为: !BACKUP_NAME!
    )

    if errorlevel 2 (
        :: 跳过
        echo %YELLOW%[WARN]%NC% 已跳过安装
        goto :success_exit
    )

    if errorlevel 1 (
        :: 覆盖
        rmdir /s /q "%TARGET_PATH%" >nul 2>&1
        if errorlevel 1 (
            echo %RED%[ERR]%NC% 删除旧版本失败，请检查权限
            goto :error_exit
        )
        echo %GREEN%[OK]%NC% 已删除旧版本
    )
)

:: ====================
:: 执行安装
:: ====================
echo.
echo %CYAN%正在安装...%NC%

:: 创建临时目录
set TEMP_DIR=%TEMP%\claude-skill-install-%RANDOM%
mkdir "%TEMP_DIR%" >nul 2>&1

:: 复制当前目录内容到临时目录（排除脚本自身）
for %%F in (*.*) do (
    if /i not "%%~xF"==".bat" (
        copy "%%F" "%TEMP_DIR%\" >nul 2>&1
    )
)
for /d %%D in (*) do (
    if /i not "%%D"=="%SKILL_DIR%" (
        xcopy "%%D" "%TEMP_DIR%\%%D\" /s /e /i /q >nul 2>&1
    )
)

:: 移动技能目录到目标位置
if exist "%TEMP_DIR%\%SKILL_DIR%" (
    move "%TEMP_DIR%\%SKILL_DIR%" "%SKILLS_DIR%\" >nul 2>&1
) else (
    :: 如果没有子目录，直接复制当前目录
    mkdir "%TARGET_PATH%" >nul 2>&1
    xcopy "%TEMP_DIR%\*" "%TARGET_PATH%\" /s /e /i /q >nul 2>&1
)

:: 清理临时目录
rmdir /s /q "%TEMP_DIR%" >nul 2>&1

:: 验证安装
if exist "%TARGET_PATH%\package.json" (
    echo %GREEN%[OK]%NC% 技能安装成功!
    echo     位置: %TARGET_PATH%
) else (
    echo %RED%[ERR]%NC% 安装失败，未找到 package.json
    goto :error_exit
)

:: ====================
:: 成功退出
:: ====================
:success_exit
echo.
echo %GREEN%========================================%NC%
echo %GREEN%  Installation Complete!%NC%
echo %GREEN%========================================%NC%
echo.
echo 请重启 Claude Code 或刷新 Skills 以加载新技能
echo.
pause
exit /b 0

:: ====================
:: 错误退出
:: ====================
:error_exit
echo.
echo %RED%========================================%NC%
echo %RED%  安装失败%NC%
echo %RED%========================================%NC%
echo.
echo 常见问题:
echo   1. 检查是否有足够的磁盘空间
echo   2. 检查目标目录的写入权限
echo   3. 确保 Claude Code 没有正在使用该技能
echo.
pause
exit /b 1
