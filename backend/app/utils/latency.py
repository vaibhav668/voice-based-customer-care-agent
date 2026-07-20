import time
import logging

logger = logging.getLogger("app.latency")

class LatencyTracker:
    def __init__(self, request_type: str = "VoiceTurn"):
        self.request_type = request_type
        self.start_time = time.time()
        self.stages = {}

    def log_stage(self, stage_name: str):
        self.stages[stage_name] = time.time()

    def print_summary(self):
        end_time = time.time()
        total_time = end_time - self.start_time
        sorted_stages = sorted(self.stages.items(), key=lambda x: x[1])
        
        log_lines = [
            f"=== LATENCY SUMMARY ({self.request_type}) ==="
        ]
        prev_time = self.start_time
        for stage, timestamp in sorted_stages:
            stage_duration = timestamp - prev_time
            cumulative = timestamp - self.start_time
            log_lines.append(f"  - {stage:<25}: {stage_duration*1000:7.2f} ms (cumulative: {cumulative*1000:7.2f} ms)")
            prev_time = timestamp
            
        remaining = end_time - prev_time
        log_lines.append(f"  - {'Response Sent':<25}: {remaining*1000:7.2f} ms")
        log_lines.append(f"  * {'TOTAL TURN LATENCY':<25}: {total_time*1000:7.2f} ms")
        log_lines.append("=========================================")
        
        logger.info("\n".join(log_lines))
