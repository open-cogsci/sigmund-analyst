import os
from jupyter_client.kernelspec import KernelSpecManager
import logging
logger = logging.getLogger(__name__)


class HomeAwareKernelSpecManager(KernelSpecManager):
    """Reimplements the KernelSpecManager to always search in the Linux home
    folder. This for example ensures that the local kernels are picked up in a
    flatpak environment.
    """
    def _kernel_dirs_default(self) -> list[str]:
        dirs = super()._kernel_dirs_default()
        home_dir = os.path.expanduser("~")
        jupyter_kernel_dir = os.path.join(
            home_dir, '.local', 'share', 'jupyter', 'kernels')
        if os.path.isdir(jupyter_kernel_dir) and os.access(jupyter_kernel_dir,
                                                           os.R_OK):
            if jupyter_kernel_dir not in dirs:
                dirs.append(jupyter_kernel_dir)
        return dirs
