import re

_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def parse_train_log_line(line: str):
    result = {}

    progress_match = re.search(r'(\d+)/(\d+)\s+\[', line)
    if progress_match:
        result['current_step'] = int(progress_match.group(1))
        result['total_steps'] = int(progress_match.group(2))
        if result['total_steps'] > 0:
            result['progress'] = result['current_step'] / result['total_steps']

    # Values may be quoted, for example: {'loss': '0.6408'}.
    loss_match = re.search(
        rf"[\"']loss[\"']\s*:\s*[\"']?({_NUMBER})[\"']?",
        line,
        re.IGNORECASE,
    )
    if loss_match:
        result['current_loss'] = float(loss_match.group(1))

    epoch_match = re.search(
        rf"[\"']epoch[\"']\s*:\s*[\"']?({_NUMBER})(?:\s*/\s*({_NUMBER}))?[\"']?",
        line,
        re.IGNORECASE,
    )
    if epoch_match:
        epoch = float(epoch_match.group(1))
        result['epoch'] = epoch
        result['current_epoch'] = int(epoch)
        if epoch_match.group(2) is not None:
            result['total_epochs'] = int(float(epoch_match.group(2)))

    if '***** train running metrics *****' in line or 'saved' in line.lower():
        result['finished'] = True

    return result if result else None


def parse_api_health_output(line: str) -> bool:
    return 'Uvicorn running on' in line or 'Application startup complete' in line
