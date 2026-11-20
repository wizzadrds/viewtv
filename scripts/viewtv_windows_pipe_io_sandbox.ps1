# VIEWTV — bounded asynchronous named-pipe I/O, SANDBOX ONLY.
# Deadline covers an entire message; a partial sender cannot restart the clock.
Set-StrictMode -Version Latest

function Read-ViewtvPipeTestExact(
    [IO.Stream]$Stream, [int]$ByteCount, [int]$DeadlineMs
) {
    if ($ByteCount -lt 0 -or $ByteCount -gt 8192 -or
        $DeadlineMs -lt 250 -or $DeadlineMs -gt 15000) {
        throw 'Límites de lectura de pipe inválidos.'
    }
    $data = [byte[]]::new($ByteCount)
    $index = 0
    $watch = [Diagnostics.Stopwatch]::StartNew()
    while ($index -lt $ByteCount) {
        $timeLeft = $DeadlineMs - [int]$watch.ElapsedMilliseconds
        if ($timeLeft -le 0) { throw [TimeoutException]::new('Lectura de pipe agotada.') }
        $operation = $Stream.ReadAsync($data, $index, $ByteCount-$index)
        if (-not $operation.Wait($timeLeft)) {
            throw [TimeoutException]::new('Lectura de pipe agotada.')
        }
        $count = [int]$operation.Result
        if ($count -le 0) { throw [IO.EndOfStreamException]::new('Lectura incompleta.') }
        $index += $count
    }
    return ,$data
}

function Read-ViewtvPipeTestFrame([IO.Stream]$Stream,[int]$DeadlineMs) {
    # Use one global deadline; four-byte header + body share the time budget.
    if ($DeadlineMs -lt 250 -or $DeadlineMs -gt 15000) {
        throw 'Tiempo de lectura de pipe inválido.'
    }
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $header = Read-ViewtvPipeTestExact $Stream 4 $DeadlineMs
    $length = [BitConverter]::ToInt32($header,0)
    if ($length -lt 2 -or $length -gt 8192) {
        return [pscustomobject]@{TooLargeOrInvalid=$true; Data=[byte[]]::new(0)}
    }
    $rest = $DeadlineMs - [int]$watch.ElapsedMilliseconds
    if ($rest -lt 250) {
        throw [TimeoutException]::new('Tiempo de mensaje agotado.')
    }
    $payload = Read-ViewtvPipeTestExact $Stream $length $rest
    return [pscustomobject]@{TooLargeOrInvalid=$false; Data=$payload}
}
