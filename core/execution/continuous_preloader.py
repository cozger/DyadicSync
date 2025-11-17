"""
Continuous Preloader for Zero-ISI Stimulus Presentation.

This module provides phase-agnostic preloading that continuously stays aware
of "what's next" and loads resources in the background during current phase display.

Phase 3 Feature: Eliminates unintended interstimulus intervals (ISI) by borrowing
time from previous phases to complete all preparation (loading + sync).
"""

import time
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Optional

logger = logging.getLogger(__name__)


class ContinuousPreloader:
    """
    Manages continuous background preloading of upcoming phases.

    Features:
    - Phase-agnostic: Works with any Phase implementing prepare()
    - Two-stage orchestration: Resource loading + sync preparation
    - Thread-safe: Preloading happens in background without blocking
    - Continuous awareness: Always knows and prepares "what's next"

    Example:
        preloader = ContinuousPreloader(device_manager)

        # During fixation, submit next video for preloading
        preloader.preload_next(next_video_phase, when=time.time() + 0.2)

        # Before video starts, ensure preload complete
        preloader.wait_for_preload(timeout=10.0)

        # Video phase executes instantly (resources already loaded)
        video_phase.execute(device_manager, lsl_outlet)
    """

    def __init__(self, device_manager):
        """
        Initialize continuous preloader.

        Args:
            device_manager: DeviceManager instance for resource creation
        """
        self.device_manager = device_manager
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="Preloader")
        self.current_preload_future: Optional[Future] = None
        self.current_phase_name: Optional[str] = None
        self._shutdown = False

    def preload_next(self, next_phase, when: Optional[float] = None):
        """
        Submit next phase for background preloading (STAGE 1: Resource Loading).

        This schedules resource loading (videos, audio) to happen during the
        current phase's display time, eliminating ISI gaps.

        Args:
            next_phase: Phase instance to preload
            when: Timestamp when to start preloading (default: immediately)
                  Example: time.time() + 0.2 (start in 200ms)

        Example:
            # During fixation (T=0.2s into 3s duration)
            preloader.preload_next(video_phase, when=time.time() + 0.2)
            # Preloading starts at T=0.4s, completes by T=2.4s
            # Fixation ends at T=3.0s → video starts instantly
        """
        if self._shutdown:
            logger.warning("Preloader already shut down, ignoring preload request")
            return

        if not next_phase.needs_preload():
            logger.debug(f"{next_phase.name}: No preload needed, skipping")
            return

        # HIGH PRIORITY FIX #8: Cancel any pending preload (phase sequence changed)
        if self.current_preload_future and not self.current_preload_future.done():
            logger.info(f"Canceling previous preload: {self.current_phase_name}")
            canceled = self.current_preload_future.cancel()

            if not canceled:
                # Already running, can't cancel - wait for completion with timeout
                logger.warning(
                    f"Previous preload ({self.current_phase_name}) already running, "
                    f"waiting for completion..."
                )
                try:
                    self.current_preload_future.result(timeout=1.0)
                    logger.info(f"Previous preload completed during cancellation")
                except TimeoutError:
                    logger.warning(f"Previous preload timeout during cancellation (1s)")
                except Exception as e:
                    logger.warning(f"Previous preload cleanup error: {e}")

        self.current_phase_name = next_phase.name

        def preload_worker():
            """Background worker that loads resources at scheduled time."""
            try:
                # Wait until scheduled time (if specified)
                if when:
                    delay = when - time.time()
                    if delay > 0:
                        logger.debug(f"{next_phase.name}: Waiting {delay*1000:.0f}ms before preload")
                        time.sleep(delay)

                # STAGE 1: Load heavy resources (videos, audio)
                prep_start = time.time()
                prep_duration = next_phase.prepare(self.device_manager)
                total_duration = time.time() - prep_start

                logger.info(
                    f"{next_phase.name}: STAGE 1 complete "
                    f"(prep={prep_duration*1000:.1f}ms, total={total_duration*1000:.1f}ms)"
                )

            except Exception as e:
                logger.error(f"{next_phase.name}: Preload failed: {e}", exc_info=True)

        # Submit preload task to background thread
        self.current_preload_future = self.executor.submit(preload_worker)
        logger.debug(f"{next_phase.name}: Preload submitted")

    def wait_for_preload(self, timeout: float = 10.0) -> bool:
        """
        Block until current preload completes.

        Should be called before phase.execute() to ensure resources are loaded.
        In typical cases (proper time-borrowing), this returns immediately because
        preloading completed during previous phase.

        Args:
            timeout: Maximum seconds to wait (default: 10s)

        Returns:
            True if preload completed successfully, False if timeout/error

        Example:
            # Before video starts
            preloader.wait_for_preload(timeout=5.0)
            # Resources guaranteed loaded (or timeout logged)
        """
        if not self.current_preload_future:
            return True  # No preload in progress

        try:
            wait_start = time.time()
            self.current_preload_future.result(timeout=timeout)
            wait_duration = time.time() - wait_start

            if wait_duration > 0.050:  # More than 50ms wait
                logger.warning(
                    f"{self.current_phase_name}: Had to wait {wait_duration*1000:.1f}ms for preload "
                    f"(preload not finished during previous phase)"
                )
            else:
                logger.debug(
                    f"{self.current_phase_name}: Preload already complete "
                    f"(wait={wait_duration*1000:.1f}ms)"
                )

            return True

        except TimeoutError:
            logger.error(
                f"{self.current_phase_name}: Preload timeout after {timeout}s! "
                f"This will cause ISI delay."
            )
            return False

        except Exception as e:
            logger.error(
                f"{self.current_phase_name}: Preload error: {e}",
                exc_info=True
            )
            return False

    def shutdown(self):
        """
        Shutdown preloader and wait for pending tasks.

        Call this at the end of experiment execution.
        """
        if self._shutdown:
            return

        logger.info("Shutting down ContinuousPreloader")
        self._shutdown = True

        # Wait for current preload to finish
        if self.current_preload_future:
            try:
                self.current_preload_future.result(timeout=5.0)
            except Exception as e:
                logger.warning(f"Error waiting for preload during shutdown: {e}")

        # Shutdown thread pool
        self.executor.shutdown(wait=True)
        logger.info("ContinuousPreloader shut down")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup."""
        self.shutdown()
        return False
