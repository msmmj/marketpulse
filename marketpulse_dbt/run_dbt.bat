@echo off
for /d /r . %%d in (.ipynb_checkpoints) do @if exist "%%d" rmdir /s /q "%%d"
dbt %*