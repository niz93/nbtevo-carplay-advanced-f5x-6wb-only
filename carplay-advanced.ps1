# Windows PowerShell 5.1 client for st1ng/nbtevo-carplay-advanced.
# The original carplay-advanced.sh is uploaded unchanged and runs only on QNX.
# Requires Windows OpenSSH, ENET network, enabled HU SSH and an authenticated SSH client.
Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $Root 'plugin'
$QnxScript = Join-Path $Root 'carplay-advanced.sh'
$BackupRoot = Join-Path $Root 'BACKUP'
$Stage = '/fs/sda1/opt/carplay-advanced-upload'
$script:NodePrefix = ''
$script:SshExe = ''
$script:SshKey = ''
$script:TargetHost = 'root@169.254.199.99'
$script:TargetPort = 22
$script:SshProfile = 'legacy-rsa'
$Full = @('CarPlayMenu.manifest','CarPlayMenu.xml','CarPlayMenu_ALL_Texts.zip','libCarPlayMenu.so','librghook.so','librghook-kombi.so','librghook-most.so','librghook-both.so','libcppinch.so','libcpreboot.so','libcpprobe.so','boot.sh','restart.sh')
$Hud = @('librghook.so','librghook-kombi.so','librghook-most.so','librghook-both.so','libcpprobe.so','libcpreboot.so','boot.sh','CarPlayMenu.manifest','CarPlayMenu-hud.xml','CarPlayMenu_ALL_Texts.zip','libCarPlayMenu-hud.so')
$FullLib = @('libCarPlayMenu.so','librghook.so','librghook-kombi.so','librghook-most.so','librghook-both.so','libcppinch.so','libcpreboot.so','libcpprobe.so')
$HudLib = @('librghook.so','librghook-kombi.so','librghook-most.so','librghook-both.so','libcpprobe.so','libCarPlayMenu-hud.so')
$SystemPaths = @('/bin/start_screen.sh','/opt/conn/bin/carplay/mm-ipod','/opt/conn/bin/Connectivity','/opt/conn/data/carplay/carplay.ini','/opt/hmi/data/ro/mini/id5/widget/generated/Spec_State_Merged.pbw','/opt/hmi/ID5/data/ro/mini/id5/widget/generated/Spec_State_Merged.pbw','/opt/hmi/data/ro/common/widget/generated/Spec_State_Merged.pbw','/opt/hmi/ID5/data/ro/common/widget/generated/Spec_State_Merged.pbw')
$BackupFolders = @('/var/opt/hmi/data/rw/Plugins/CarPlayMenu','/var/opt/hmi/data/rw/carplaymenu','/var/opt/carplay-advanced-backups/originals')
function Info([string]$s) { Write-Host ('[+] '+$s) }
function Fail([string]$s) { throw $s }
function Help {
@'
Windows CarPlay Advanced / PowerShell 5.1 (experimental client)
  .\carplay-advanced.ps1 ssh-check|ssh-shell|install|uninstall|status|restart|hud-probe [options]
  .\carplay-advanced.ps1 self-test
  --proxy              TurboCode Proxy: root@127.0.0.1 port 6969 + legacy-dss
  --host user@ip       default root@169.254.199.99
  --port number        default 22 (or 6969 with --proxy)
  --ssh-profile name   legacy-rsa (default), legacy-dss, modern
  --key private-key    optional OpenSSH key (or use configured ssh-agent)
  SSH uses Windows ssh.exe only. No PuTTY/WSL/Git Bash required.
  ssh-check verifies HU identity via interactive SSH; ssh-shell opens QNX shell.
  status/install/uninstall require noninteractive SSH key/agent authentication.
  --full | --hud       default full for ID5, hud for ID6
  --cluster most|kombi|both
  --hud-tx 0|4          set MOST HUDTerminal DSI transmissionType (4 experimental, based on external F60 evidence)
  --dry-run            check remote QNX install plan without committing
  --yes                skip the Windows confirmation prompt
  --restart-hmi        restart HU after a successful install/uninstall
  --keep-config        retain switch settings on uninstall
  --help
IMPORTANT: this native port deliberately refuses unknown ID5 full HMI builds.
The upstream HMI instruction-pattern scanner is not implemented on Windows yet.
Sq00ky proxy: ssh root@127.0.0.1 -p 6969 -o HostKeyAlgorithms=+ssh-dss -m hmac-sha1
Check interactive connection first: .\carplay-advanced.ps1 ssh-check --proxy
'@ | Write-Host
}
function Hex([byte[]]$b) { [BitConverter]::ToString($b).Replace('-','').ToLowerInvariant() }
function Bytes([string]$f,[int]$start,[int]$count) {
    $s=[IO.File]::OpenRead($f)
    try {
        if ($s.Length -lt $start+$count) { Fail "Truncated $f" }
        [void]$s.Seek($start,[IO.SeekOrigin]::Begin)
        $arr=New-Object byte[] $count
        if ($s.Read($arr,0,$count) -ne $count) { Fail "Read failed $f" }
        return ,$arr
    } finally { $s.Dispose() }
}
function Hash([string]$f) { (Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash.ToLowerInvariant() }
function Validate([string]$mode) {
    $files=if($mode -eq 'hud'){$Hud}else{$Full}
    $libs=if($mode -eq 'hud'){$HudLib}else{$FullLib}
    foreach($name in $files) {
        $f=Join-Path $Source $name
        if(-not (Test-Path -LiteralPath $f -PathType Leaf)) { Fail "Missing plugin file: $name" }
        $item=Get-Item -LiteralPath $f
        if($item.Length -eq 0 -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { Fail "Empty or linked file: $name" }
    }
    foreach($name in $libs) {
        $f=Join-Path $Source $name
        if((Hex (Bytes $f 0 7)) -ne '7f454c46010101') { Fail "Not ELF32 LE: $name" }
        if((Hex (Bytes $f 16 4)) -ne '03002800') { Fail "Not ARM DYN: $name" }
        if((Hex (Bytes $f 40 2)) -ne '3400') { Fail "Invalid ELF header: $name" }
    }
    if((Hex (Bytes (Join-Path $Source 'CarPlayMenu_ALL_Texts.zip') 0 4)) -ne '504b0304') { Fail 'Invalid ZIP' }
    if((Get-Content -LiteralPath (Join-Path $Source 'CarPlayMenu.manifest') -Raw) -notmatch '<name>CarPlayMenu</name>') { Fail 'Invalid manifest' }
    $xml=if($mode -eq 'hud'){'CarPlayMenu-hud.xml'}else{'CarPlayMenu.xml'}
    if((Get-Content -LiteralPath (Join-Path $Source $xml) -Raw) -notmatch 'pluginApp') { Fail "Invalid $xml" }
    Info "Validated $($files.Count) local files ($mode)"
}
function Supported {
    $table=@{}
    foreach($line in [IO.File]::ReadAllLines($QnxScript)) {
        if($line -match '^(\S+)\s+(HmiMain3D|libconn_carplay\.so|scan)\s+([a-f0-9]{64}|none)\s*$') {
            $name=$matches[1];$field=$matches[2];$sum=$matches[3]
            if(-not $table.ContainsKey($name)){$table[$name]=@{}}
            $table[$name][$field]=$sum
        }
    }
    return $table
}
function IsId6([string]$path) {
    $rx='711c09e308009015003090e50c3093e533ff2fe1000050e3(?:0150a013|0160a013|01e0a013|01c0a013)'
    $f=[IO.File]::OpenRead($path)
    try {
        $block=2*1024*1024;$buf=New-Object byte[] ($block+64);$carry=0
        while($true) {
            $n=$f.Read($buf,$carry,$block)
            if($n -eq 0){break}
            $len=$carry+$n
            if([regex]::IsMatch(([BitConverter]::ToString($buf,0,$len).Replace('-','').ToLowerInvariant()),$rx)){return $true}
            $carry=[Math]::Min($len,64)
            [Array]::Copy($buf,$len-$carry,$buf,0,$carry)
        }
    } finally {$f.Dispose()}
    return $false
}
function QuoteArg([string]$s) { return '"' + $s.Replace('"','\"') + '"' }
function SshOptions {
    # Profile only affects connections made by this installer. It does not alter
    # Windows system SSH settings. Legacy algorithms must be explicitly scoped.
    $opts=@('-p', [string]$script:TargetPort)
    switch($script:SshProfile) {
        'legacy-dss' { $opts+=@('-o','HostKeyAlgorithms=+ssh-dss','-o','MACs=hmac-sha1','-o','PubkeyAcceptedAlgorithms=+ssh-rsa') }
        'legacy-rsa' { $opts+=@('-o','HostKeyAlgorithms=+ssh-rsa','-o','PubkeyAcceptedAlgorithms=+ssh-rsa') }
        'modern' { }
        default { Fail "Invalid SSH profile $script:SshProfile" }
    }
    return $opts
}
function InteractiveSsh([bool]$shell) {
    # No BatchMode and no redirected stdin: the Windows terminal may ask for
    # a password. ssh-check reads uname -n only; ssh-shell opens manual session.
    Info ("Connecting to {0}:{1} ({2})" -f $script:TargetHost,$script:TargetPort,$script:SshProfile)
    CheckNet
    $argv=@($(if($shell){'-t'}else{'-T'}),'-o','ConnectTimeout=12','-o','StrictHostKeyChecking=ask')+(SshOptions)
    if($script:SshKey){$argv+=@('-i',$script:SshKey)}
    $argv+=@($script:TargetHost)
    if(-not $shell){$argv+=@('uname -n')}
    & $script:SshExe @argv
    if($LASTEXITCODE -ne 0){Fail "SSH interactive check failed with exit $LASTEXITCODE"}
    if($shell){Info 'SSH shell session finished.'}
    else{Info 'SSH identity check completed. Automated install/status requires a key or agent.'}
}
function Ssh([string]$remote,[string]$inputFile='',[string]$outputFile='',[int]$timeout=180) {
    $si=New-Object Diagnostics.ProcessStartInfo
    $si.FileName=$script:SshExe
    $si.UseShellExecute=$false
    $si.CreateNoWindow=$true
    $si.RedirectStandardInput=$true
    $si.RedirectStandardOutput=$true
    $si.RedirectStandardError=$false
    # Windows OpenSSH intentionally does not use Unix ControlMaster connection sharing.
    # BatchMode prevents hanging on unattended password prompts during binary transfers.
    # Trust the HU host key in an interactive Windows Terminal session first.
    $si.Arguments='-T -o BatchMode=yes -o LogLevel=ERROR -o ConnectTimeout=12 -o StrictHostKeyChecking=yes -o ServerAliveInterval=10 -o ServerAliveCountMax=3'
    foreach($opt in (SshOptions)){$si.Arguments+=' '+(QuoteArg $opt)}
    if($script:SshKey){$si.Arguments+=' -i '+(QuoteArg $script:SshKey)}
    $si.Arguments+=' '+(QuoteArg $script:TargetHost)+' '+(QuoteArg $remote)
    $proc=New-Object Diagnostics.Process;$proc.StartInfo=$si
    $output=$null;$input=$null
    try {
        if(-not $proc.Start()){Fail 'ssh.exe start failed'}
        if($outputFile){
            $dir=Split-Path -Parent $outputFile
            if($dir){[void](New-Item -Path $dir -ItemType Directory -Force)}
            $output=[IO.File]::Create($outputFile)
        }else{$output=New-Object IO.MemoryStream}
        $task=$proc.StandardOutput.BaseStream.CopyToAsync($output)
        if($inputFile){
            $input=[IO.File]::OpenRead($inputFile)
            $input.CopyTo($proc.StandardInput.BaseStream)
            $input.Dispose();$input=$null
        }
        $proc.StandardInput.Close()
        if(-not $proc.WaitForExit($timeout*1000)){
            try{$proc.Kill()}catch{}
            Fail "SSH timeout: $remote"
        }
        $task.GetAwaiter().GetResult()
        if($outputFile){$output.Flush();return @{Exit=$proc.ExitCode;Text=''}}
        return @{Exit=$proc.ExitCode;Text=[Text.Encoding]::UTF8.GetString(([IO.MemoryStream]$output).ToArray())}
    }finally{
        if($input){$input.Dispose()}
        if($output){$output.Dispose()}
        $proc.Dispose()
    }
}
function Remote([string]$cmd,[string]$inputFile='',[string]$outputFile='',[int]$timeout=180){
    return Ssh ($script:NodePrefix+$cmd) $inputFile $outputFile $timeout
}
function RemoteOK([string]$cmd){$r=Remote $cmd;return ($r.Exit -eq 0)}
function RemoteText([string]$cmd){
    $r=Remote $cmd
    if($r.Exit -ne 0){Fail "QNX command failed: $cmd"}
    return $r.Text.Trim()
}
function Pull([string]$from,[string]$to) {
    $r=Remote ('/bin/cat '+$from) '' $to 600
    if($r.Exit -ne 0){Fail "QNX read failed: $from"}
    $size=(RemoteText ("/bin/ksh -c 'wc -c < $from'")).Trim()
    if($size -notmatch '^\d+$'){Fail "Invalid remote size for $from"}
    if((Get-Item -LiteralPath $to).Length -ne [long]$size){Fail "File size differs: $from"}
}
function Push([string]$from,[string]$to) {
    $r=Remote ("/bin/ksh -c 'cat > $to'") $from '' 240
    if($r.Exit -ne 0){Fail "QNX upload failed: $to"}
    $tmp=[IO.Path]::GetTempFileName()
    try{
        Pull $to $tmp
        if((Hash $tmp) -ne (Hash $from)){Fail "Upload hash mismatch: $to"}
    }finally{Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue}
}
function Tree([string]$remoteBase,[string]$localBase) {
    $walk='walk() { for f in "$1"/*; do if [ -d "$f" ] && [ ! -L "$f" ]; then echo "D $f"; walk "$f"; elif [ -f "$f" ]; then echo "F $f"; fi; done; }; walk '+$remoteBase
    $r=Remote ("/bin/ksh -c '$walk'") '' '' 300
    if($r.Exit -ne 0){Fail "QNX tree listing failed: $remoteBase"}
    [void](New-Item -Path $localBase -ItemType Directory -Force)
    foreach($line in ($r.Text -split '\r?\n')){
        if(-not $line.Trim()){continue}
        if($line -notmatch '^([DF]) (/.+)$'){Fail "Invalid remote tree record: $line"}
        $kind=$matches[1];$full=$matches[2]
        if(-not $full.StartsWith($remoteBase+'/')){Fail "Untrusted remote file path: $full"}
        $rel=$full.Substring($remoteBase.Length+1)
        if($rel -match '(^|/)\.\.(/|$)|[\\:]'){Fail "Unsafe path: $full"}
        $dest=Join-Path $localBase ($rel.Replace('/','\'))
        if($kind -eq 'D'){[void](New-Item -Path $dest -ItemType Directory -Force)}
        else{Pull $full $dest}
    }
}
function BackupBefore([string]$action){
    $base=Join-Path $BackupRoot ((Get-Date -Format 'yyyyMMdd-HHmmss')+'-'+$action+'-before')
    [void](New-Item -ItemType Directory -Path (Join-Path $base 'system') -Force)
    $manifest=New-Object 'System.Collections.Generic.List[string]'
    foreach($f in $SystemPaths){
        $state=RemoteText ("/bin/ksh -c 'if [ -L $f ]; then echo link; elif [ -f $f ]; then echo file; else echo absent; fi'")
        if($state -eq 'file'){
            Pull $f (Join-Path (Join-Path $base 'system') ($f.TrimStart('/').Replace('/','\')))
            $manifest.Add("file $f")
        }elseif($state -eq 'link'){$manifest.Add("link $f")}
        elseif($state -eq 'absent'){$manifest.Add("absent $f")}
        else{Fail "Unknown remote state: $f"}
    }
    foreach($d in $BackupFolders){
        if(RemoteOK ("/bin/ksh -c '[ -d $d ]'")){
            Tree $d (Join-Path (Join-Path $base 'folders') ($d.TrimStart('/').Replace('/','\')))
            $manifest.Add("folder $d")
        }else{$manifest.Add("absent $d")}
    }
    [IO.File]::WriteAllLines((Join-Path $base 'manifest.txt'),$manifest.ToArray(),(New-Object Text.UTF8Encoding($false)))
    Info "Pre-change backup: $base"
    return $base
}
function RemoteHash([string]$path){
    if(-not (RemoteOK ("/bin/ksh -c '[ -f $path ]'"))){return 'missing'}
    $temp=[IO.Path]::GetTempFileName()
    try{Pull $path $temp;return (Hash $temp)}
    finally{Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue}
}
function Detect([string]$mode,[string]$action,[string]$work){
    $hmi='/opt/hmi/bin/zipped/HmiMain3D'
    if(-not (RemoteOK ("/bin/ksh -c '[ -f $hmi ]'"))){$hmi='/opt/hmi/bin/HmiMain3D'}
    $ver=(Remote '/bin/cat /opt/hmi/ID5/data/ro/version.txt').Text.Trim()
    $local=Join-Path $work 'HmiMain3D'
    Info 'Reading HmiMain3D from NBT EVO (~60 MB)'
    Pull $hmi $local
    $kind=if(IsId6 $local){'id6'}else{'id5'}
    if(-not $mode){$mode=if($kind -eq 'id6'){'hud'}else{'full'}}
    Info "Detected $kind; mode=$mode; version=$ver"
    $mm='/opt/conn/bin/carplay/mm-ipod'
    if(RemoteOK "/bin/ksh -c '[ -L $mm ] && [ -f /var/opt/hmi/data/rw/carplaymenu/bin/mm-ipod ]'"){$mm='/var/opt/hmi/data/rw/carplaymenu/bin/mm-ipod'}
    Info "mm-ipod SHA256: $(RemoteHash $mm)"
    $sw=''
    if($mode -eq 'full' -and $kind -eq 'id5'){
        $h1=Hash $local
        $h2=RemoteHash '/opt/conn/lib/carplay/devctrl/libconn_carplay.so'
        Info "HMI SHA256: $h1";Info "libconn_carplay.so SHA256: $h2"
        foreach($name in (Supported).Keys){
            $item=(Supported)[$name]
            if($item['HmiMain3D'] -eq $h1 -and $item['libconn_carplay.so'] -eq $h2){$sw=$name;break}
        }
        if(-not $sw -and $action -eq 'install'){Fail 'Unknown ID5 HMI hashes. Full mode refused; native Windows port does not have the upstream pattern scanner. Use --hud.'}
        if($sw){Info "Hash-supported software: $sw"}
    }
    return @{Kind=$kind;Mode=$mode;Software=$sw;Version=$ver}
}
function CheckNet(){
    $name=($script:TargetHost -split '@')[-1]
    $client=New-Object Net.Sockets.TcpClient
    try{
        $ar=$client.BeginConnect($name,$script:TargetPort,$null,$null)
        if(-not $ar.AsyncWaitHandle.WaitOne(4500)){Fail "Cannot reach ${name}:$($script:TargetPort): check ENET/proxy and SSH"}
        $client.EndConnect($ar)
    }finally{$client.Close()}
}
function RunQnx([string]$action,[string]$opts,[bool]$reboot){
    $cmd="/bin/sh $Stage/carplay-advanced.sh $action $opts"
    $result=Remote $cmd '' '' $(if($reboot){85}else{360})
    if($result.Text){Write-Host $result.Text.TrimEnd()}
    if($reboot -and $result.Text -match 'rebooting the head unit|Restarting the head unit|restarting'){return $result}
    if($result.Exit -ne 0){Fail "QNX installer failed with exit $($result.Exit)"}
    return $result
}
function Main {
    if($args.Count -eq 0){Help;return}
    $action=[string]$args[0];$mode='';$dry=$false;$yes=$false;$restart=$false;$keep=$false;$cluster='';$hudTx='';$proxy=$false;$portSet=$false;$profileSet=$false
    for($i=1;$i -lt $args.Count;$i++){
        $part=[string]$args[$i]
        switch -Exact ($part){
            '--host' {if($i+1 -ge $args.Count){Fail '--host needs value'};$i++;$script:TargetHost=[string]$args[$i]}
            '--proxy' {$proxy=$true}
            '--port' {if($i+1 -ge $args.Count){Fail '--port needs 1..65535'};$i++;$portSet=$true;$script:TargetPort=[int]::Parse([string]$args[$i])}
            '--ssh-profile' {if($i+1 -ge $args.Count){Fail '--ssh-profile needs legacy-rsa|legacy-dss|modern'};$i++;$profileSet=$true;$script:SshProfile=[string]$args[$i]}
            '--key' {if($i+1 -ge $args.Count){Fail '--key needs value'};$i++;$script:SshKey=[string]$args[$i]}
            '--full' {$mode='full'}
            '--hud' {$mode='hud'}
            '--dry-run' {$dry=$true}
            '--yes' {$yes=$true}
            '-y' {$yes=$true}
            '--restart-hmi' {$restart=$true}
            '--keep-config' {$keep=$true}
            '--cluster' {if($i+1 -ge $args.Count){Fail '--cluster needs value'};$i++;$cluster=[string]$args[$i]}
            '--hud-tx' {if($i+1 -ge $args.Count){Fail '--hud-tx needs 0 or 4'};$i++;$hudTx=[string]$args[$i]}
            '--help' {Help;return}
            default {Fail "Unknown option: $part"}
        }
    }
    if($action -in @('--help','-h')){Help;return}
    if($action -notin @('install','uninstall','status','restart','hud-probe','ssh-check','ssh-shell','self-test')){Help;Fail "Unknown action $action"}
    if($keep -and $action -ne 'uninstall'){Fail '--keep-config only valid with uninstall'}
    if($restart -and $action -notin @('install','uninstall')){Fail '--restart-hmi needs install/uninstall'}
    if($cluster -and $cluster -notin @('most','kombi','both')){Fail '--cluster must be most|kombi|both'}
    if($hudTx -and $hudTx -notin @('0','4')){Fail '--hud-tx must be 0 or 4'}
    if($hudTx -and $action -ne 'install'){Fail '--hud-tx requires install'}
    if($proxy){
        if($script:TargetHost -ne 'root@169.254.199.99'){Fail '--proxy cannot be combined with --host; use --host root@127.0.0.1 --port 6969 instead'}
        $script:TargetHost='root@127.0.0.1'
        if(-not $portSet){$script:TargetPort=6969}
        if(-not $profileSet){$script:SshProfile='legacy-dss'}
    }
    if($script:TargetPort -lt 1 -or $script:TargetPort -gt 65535){Fail '--port must be between 1 and 65535'}
    if($script:SshProfile -notin @('legacy-rsa','legacy-dss','modern')){Fail '--ssh-profile must be legacy-rsa, legacy-dss or modern'}
    if($script:TargetHost -notmatch '^[A-Za-z_][A-Za-z_0-9-]*@[A-Za-z0-9][A-Za-z0-9.-]*$'){Fail 'Invalid host'}
    if(-not (Test-Path -LiteralPath $QnxScript -PathType Leaf)){Fail 'Original QNX installer missing'}
    if($action -eq 'self-test'){
        Validate 'full';Validate 'hud'
        $t=Supported
        if($t.Count -lt 3){Fail 'Supported HMI hash table missing'}
        Info "Offline tests PASS: $($t.Count) supported HMI builds"
        return
    }
    if($script:SshKey){
        if(-not (Test-Path -LiteralPath $script:SshKey -PathType Leaf)){Fail 'SSH key path missing'}
        $script:SshKey=(Resolve-Path -LiteralPath $script:SshKey).Path
    }
    $ssh=Get-Command 'ssh.exe' -ErrorAction SilentlyContinue
    if(-not $ssh){Fail 'Windows OpenSSH Client (ssh.exe) not installed'}
    $script:SshExe=$ssh.Source
    if($action -in @('ssh-check','ssh-shell')){InteractiveSsh ($action -eq 'ssh-shell');return}
    if($action -eq 'install'){
        if($mode){Validate $mode}else{Validate 'full';Validate 'hud'}
    }
    Info "Connecting to $($script:TargetHost):$($script:TargetPort) ($($script:SshProfile))"
    CheckNet
    $node=Ssh 'uname -n'
    if($node.Exit -ne 0){Fail 'Noninteractive OpenSSH login failed. Run ssh-check with the same --proxy/--host/--port/--ssh-profile arguments; installation additionally requires a working SSH key/agent (BatchMode=yes).'}
    $name=$node.Text.Trim()
    if($name -match '^hu-omap(\.|$)'){$script:NodePrefix=''}
    elseif($name -match '^hu-jacinto(\.|$)'){$script:NodePrefix='on -f hu-omap '}
    else{Fail "Unexpected SSH device: $name"}
    Info "Connected: $name -> hu-omap"
    $work=Join-Path $env:TEMP ('cpa-win-'+[guid]::NewGuid().ToString('N'))
    [void](New-Item -Path $work -ItemType Directory -Force)
    $staged=$false
    try{
        $detect=@{Kind='id5';Mode='full';Software=''}
        if($action -in @('install','status')){$detect=Detect $mode $action $work;$mode=$detect.Mode}
        if($action -eq 'install'){
            Validate $mode
            if(-not $dry -and -not $yes){
                $answer=Read-Host "Install $mode on $script:TargetHost after Windows backup? [y/N]"
                if($answer -notmatch '^[yY]'){Fail 'Cancelled before changes'}
            }
        }
        if($action -eq 'uninstall' -and -not $dry -and -not $yes){
            $answer=Read-Host "Uninstall on $script:TargetHost after Windows backup? [y/N]"
            if($answer -notmatch '^[yY]'){Fail 'Cancelled before changes'}
        }
        if($action -in @('install','uninstall') -and -not $dry){[void](BackupBefore $action)}
        if(-not (RemoteOK "/bin/ksh -c 'rm -rf $Stage; mkdir -p $Stage/CarPlayMenu'")){Fail 'QNX staging failed'}
        $staged=$true
        Push $QnxScript "$Stage/carplay-advanced.sh"
        if($action -eq 'install'){
            $names=if($mode -eq 'hud'){$Hud}else{$Full}
            foreach($f in $names){Push (Join-Path $Source $f) "$Stage/CarPlayMenu/$f"}
            Info "Uploaded and verified $($names.Count) plugin files"
        }
        if($action -eq 'restart'){
            $lib=Join-Path $Source 'libcpreboot.so'
            if(Test-Path -LiteralPath $lib){Push $lib "$Stage/libcpreboot.so"}
        }
        $opts=''
        if($action -eq 'install'){
            $opts="--payload $Stage/CarPlayMenu --kind $($detect.Kind) --mode $mode"
            if($mode -eq 'full' -and $detect.Kind -eq 'id5'){$opts+=' --hmi '+$detect.Software}
        }
        if($dry){$opts+=' --dry-run'}
        if($keep){$opts+=' --keep-config'}
        if($cluster){$opts+=' --cluster '+$cluster}
        if($hudTx){$opts+=' --hud-tx '+$hudTx}
        Info "QNX: $action $opts"
        $result=RunQnx $action $opts ($action -eq 'restart')
        if($action -eq 'hud-probe'){
            [void](New-Item -Path $BackupRoot -ItemType Directory -Force)
            $log=Join-Path $BackupRoot ('hud-probe-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'.txt')
            [IO.File]::WriteAllText($log,$result.Text,(New-Object Text.UTF8Encoding($false)))
            Info "Saved HUD probe: $log"
        }
        if($action -in @('install','uninstall') -and -not $dry){
            $m=[regex]::Match($result.Text,'SUCCESS: (?:install|uninstall) completed\. Previous files: ([^ ;]+) ; system originals: ([^ \r\n]+)')
            if(-not $m.Success){Fail 'Remote transaction lacks SUCCESS backup record'}
            $prev=$m.Groups[1].Value;$orig=$m.Groups[2].Value
            if($prev -notmatch '^/var/opt/carplay-advanced-backups/[a-zA-Z0-9_-]+$' -or $orig -ne '/var/opt/carplay-advanced-backups/originals'){Fail 'Unexpected backup locations'}
            Tree $prev (Join-Path $BackupRoot ($prev.Split('/')[-1]))
            Tree $orig (Join-Path $BackupRoot 'originals')
            $log=Join-Path (Join-Path $BackupRoot ($prev.Split('/')[-1])) 'installer-output.log'
            [IO.File]::WriteAllText($log,$result.Text,(New-Object Text.UTF8Encoding($false)))
            Info 'Backups retrieved and size-verified on Windows'
        }
        if($restart -and -not $dry -and $action -in @('install','uninstall')){
            Info 'Requesting head unit reboot'
            [void](RunQnx 'restart' '' $true)
        }
        Info "Completed: $action"
    } finally {
        if($staged -and $action -ne 'restart' -and -not $restart){
            try{[void](Remote "/bin/ksh -c 'rm -rf $Stage'" '' '' 30)}
            catch{Write-Warning "Temporary QNX stage might remain: $Stage"}
        }
        Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
    }
}
try { Main @args; exit 0 }
catch { Write-Host ('ERROR: '+$_.Exception.Message) -ForegroundColor Red; exit 1 }
