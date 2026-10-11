#!/usr/bin/env python3
"""
Automated Cron Job Installer for Process Monitoring
Sets up continuous monitoring without manual intervention
"""

import subprocess
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class CronJobInstaller:
    def __init__(self):
        self.cron_jobs = [
            {
                'name': 'Monitor every 5 minutes (quick)',
                'schedule': '*/5 * * * *',
                'command': 'python3 /home/ansible/process_monitor_with_timestamps.py >> /var/log/bot_monitor_5min.log 2>&1'
            },
            {
                'name': 'Monitor every 30 minutes (detailed)',
                'schedule': '*/30 * * * *',
                'command': 'python3 /home/ansible/process_monitor_with_timestamps.py >> /var/log/bot_monitor_30min.log 2>&1'
            },
            {
                'name': 'Monitor every hour (full analysis)',
                'schedule': '0 * * * *',
                'command': 'python3 /home/ansible/process_monitor_with_timestamps.py >> /var/log/bot_monitor_hourly.log 2>&1'
            },
            {
                'name': 'Run HTTP tests every 30 minutes',
                'schedule': '*/30 * * * *',
                'command': 'python3 /home/ansible/test_http_api.py >> /var/log/bot_tests.log 2>&1'
            },
            {
                'name': 'Daily report generation (8 AM)',
                'schedule': '0 8 * * *',
                'command': 'python3 /home/ansible/process_monitor_with_timestamps.py >> /var/log/bot_monitor_daily_`date +\\%Y\\%m\\%d`.log 2>&1'
            },
            {
                'name': 'Cleanup old logs (daily)',
                'schedule': '0 2 * * *',
                'command': 'find /var/log/bot_*.log -mtime +30 -delete'
            }
        ]
    
    def get_current_crontab(self) -> str:
        """Get current crontab entries"""
        try:
            result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout
            return ""
        except Exception as e:
            logger.warning("Could not read current crontab: %s", e)
            return ""
    
    def install_cron_job(self, schedule: str, command: str) -> bool:
        """Install a single cron job"""
        try:
            current_cron = self.get_current_crontab()
            
            # Check if already installed
            if command in current_cron:
                return True
            
            # Add new job
            new_entry = f"{schedule} {command}\n"
            new_cron = current_cron + new_entry
            
            # Install
            process = subprocess.Popen(['crontab', '-'], 
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
            process.communicate(input=new_cron.encode())
            
            return process.returncode == 0
        except Exception as e:
            print(f"Error installing cron job: {e}")
            return False
    
    def install_all(self):
        """Install all monitoring cron jobs"""
        print("╔" + "="*70 + "╗")
        print("║" + " "*20 + "CRON JOB INSTALLER" + " "*33 + "║")
        print("╚" + "="*70 + "╝\n")
        
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Create log directory
        os.makedirs('/var/log', exist_ok=True)
        print(f"✓ Log directory ready: /var/log\n")
        
        print(f"{'─'*72}")
        print("INSTALLING CRON JOBS")
        print(f"{'─'*72}\n")
        
        installed = 0
        failed = 0
        
        for job in self.cron_jobs:
            print(f"Installing: {job['name']}")
            print(f"Schedule:   {job['schedule']}")
            print(f"Command:    {job['command'][:60]}...")
            
            if self.install_cron_job(job['schedule'], job['command']):
                print(f"✓ Installed\n")
                installed += 1
            else:
                print(f"✗ Failed\n")
                failed += 1
        
        print(f"{'─'*72}")
        print(f"Installation Summary: {installed} succeeded, {failed} failed")
        print(f"{'─'*72}\n")
        
        self.show_installed_jobs()
    
    def show_installed_jobs(self):
        """Display currently installed cron jobs"""
        print("Currently Installed Cron Jobs:")
        print(f"{'─'*72}\n")
        
        cron_content = self.get_current_crontab()
        
        if not cron_content.strip():
            print("No cron jobs installed\n")
            return
        
        # Filter only our jobs
        lines = cron_content.strip().split('\n')
        our_jobs = [l for l in lines if 'bot_monitor' in l or 'bot_tests' in l]
        
        if our_jobs:
            print("Bot Monitoring Jobs:")
            for i, job in enumerate(our_jobs, 1):
                print(f"{i}. {job[:70]}...")
        else:
            print("No bot monitoring jobs found (this is normal if first install)\n")
        
        print()
    
    def uninstall_all(self):
        """Remove all monitoring cron jobs"""
        print("Removing all bot monitoring cron jobs...\n")
        
        cron_content = self.get_current_crontab()
        lines = cron_content.strip().split('\n') if cron_content.strip() else []
        
        # Remove our jobs
        filtered_lines = [l for l in lines if 'bot_monitor' not in l and 'bot_tests' not in l]
        
        new_cron = '\n'.join(filtered_lines)
        if new_cron.strip():
            new_cron += '\n'
        
        process = subprocess.Popen(['crontab', '-'], 
                                  stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
        process.communicate(input=new_cron.encode())
        
        if process.returncode == 0:
            print("✓ All bot monitoring cron jobs removed\n")
        else:
            print("✗ Failed to remove cron jobs\n")
    
    def view_logs(self):
        """Display recent log entries"""
        print(f"Recent Monitoring Logs (5-min monitor):")
        print(f"{'─'*72}\n")
        
        import glob
        
        log_files = glob.glob('/var/log/bot_monitor_*.log')
        
        if not log_files:
            print("No logs found yet. Cron jobs will generate logs after first run.\n")
            return
        
        # Show most recent
        latest_log = max(log_files, key=os.path.getctime)
        
        print(f"Latest log: {latest_log}\n")
        
        try:
            with open(latest_log, 'r') as f:
                content = f.read()
                # Show last 20 lines
                lines = content.split('\n')
                recent = lines[-20:] if len(lines) > 20 else lines
                for line in recent:
                    if line.strip():
                        print(line)
        except Exception as e:
            print(f"Error reading logs: {e}\n")
        
        print()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Install/manage monitoring cron jobs')
    parser.add_argument('--install', action='store_true', help='Install all cron jobs')
    parser.add_argument('--uninstall', action='store_true', help='Remove all cron jobs')
    parser.add_argument('--show', action='store_true', help='Show installed jobs')
    parser.add_argument('--logs', action='store_true', help='View recent logs')
    
    args = parser.parse_args()
    
    installer = CronJobInstaller()
    
    if args.install:
        installer.install_all()
    elif args.uninstall:
        installer.uninstall_all()
    elif args.show:
        installer.show_installed_jobs()
    elif args.logs:
        installer.view_logs()
    else:
        # Default: install
        installer.install_all()

if __name__ == '__main__':
    main()
