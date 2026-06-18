import re

def parse_train_log_line(line: str):
    result = {}

    progress_match = re.search(r'(\d+)/(\d+)\s+\[', line)
    if progress_match:
        result['current_step'] = int(progress_match.group(1))
        result['total_steps'] = int(progress_match.group(2))
        if result['total_steps'] > 0:
            result['progress'] = result['current_step'] / result['total_steps']

    loss_match = re.search(r"'loss':\s*([\d.]+)", line)
    if loss_match:
        result['current_loss'] = float(loss_match.group(1))

    epoch_match = re.search(r"'epoch':\s*([\d.]+)/([\d.]+)", line)
    if epoch_match:
        result['current_epoch'] = int(float(epoch_match.group(1)))
        result['total_epochs'] = int(float(epoch_match.group(2)))

    if '***** train running metrics *****' in line or 'saved' in line.lower():
        result['finished'] = True

    return result if result else None


def parse_api_health_output(line: str) -> bool:
    return 'Uvicorn running on' in line or 'Application startup complete' in line
