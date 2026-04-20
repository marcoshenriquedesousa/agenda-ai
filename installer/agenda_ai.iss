; Agenda AI — Inno Setup Script
; Requer: Inno Setup 6+ (https://jrsoftware.org/isinfo.php)

#define AppName      "Agenda AI"
#define AppVersion   "1.0.0"
#define AppPublisher "Agenda AI"
#define AppExeName   "AgendaAI.exe"
#define DistDir      "..\dist\AgendaAI"

[Setup]
AppId={{E4F2A3B1-8C7D-4E9F-A012-3B4C5D6E7F89}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisherURL=https://github.com/marcoshenriquedesousa/agenda-ai
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\AgendaAI
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Instala por usuário — sem UAC
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=.
OutputBaseFilename=AgendaAI_Setup_{#AppVersion}
SetupIconFile=..\assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
; Não sobrescreve config do usuário em atualizações
UsePreviousAppDir=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon";    Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked
Name: "startupicon";   Description: "Iniciar automaticamente com o Windows";  GroupDescription: "Inicialização:"; Flags: unchecked

[Files]
; --- Executável ---
Source: "{#DistDir}\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; --- Dependências e dados (PyInstaller 6+ usa _internal/) ---
Source: "{#DistDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "config.json"

; --- Config padrão — preserva a config existente do usuário em updates ---
Source: "{#DistDir}\_internal\config.json"; DestDir: "{app}\_internal"; Flags: ignoreversion onlyifdoesntexist

[Icons]
Name: "{group}\{#AppName}";             Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\_internal\assets\icon.ico"
Name: "{group}\Configurações";          Filename: "{app}\{#AppExeName}"; Parameters: "--settings"; IconFilename: "{app}\_internal\assets\icon.ico"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}";       Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\_internal\assets\icon.ico"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}";       Filename: "{app}\{#AppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Iniciar {#AppName} agora"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Encerra o processo antes de desinstalar
Filename: "taskkill.exe"; Parameters: "/f /im {#AppExeName}"; Flags: runhidden; RunOnceId: "KillApp"

[Code]
var
  OllamaPage: TWizardPage;
  OllamaWarning: TLabel;

function OllamaInstalado: Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('cmd.exe', '/c where ollama >nul 2>&1', '', SW_HIDE, ewWaitUntilTerminated, ResultCode)
            and (ResultCode = 0);
end;

procedure InitializeWizard;
begin
  if not OllamaInstalado then begin
    OllamaPage := CreateCustomPage(wpSelectTasks,
      'Requisito: Ollama',
      'O Agenda AI precisa do Ollama para funcionar.');

    OllamaWarning := TLabel.Create(OllamaPage);
    OllamaWarning.Parent := OllamaPage.Surface;
    OllamaWarning.Left   := 0;
    OllamaWarning.Top    := 0;
    OllamaWarning.Width  := OllamaPage.SurfaceWidth;
    OllamaWarning.Height := 120;
    OllamaWarning.WordWrap := True;
    OllamaWarning.Caption :=
      'O Ollama não foi encontrado neste computador.' + #13#10 + #13#10 +
      'Após a instalação, baixe e instale o Ollama em:' + #13#10 +
      '  https://ollama.com/download' + #13#10 + #13#10 +
      'Em seguida, baixe o modelo padrão executando no terminal:' + #13#10 +
      '  ollama pull qwen2.5:7b-instruct';
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
end;
