################################################################################
#
# Copyright (C) 2016-2025 Advanced Micro Devices, Inc. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
################################################################################

import multiprocessing
import os
import sys
import time
from functools import partial
from typing import Any, Callable

from .Utilities import tqdm


load_average_supported = hasattr(os, 'getloadavg')
delays = 0
nix_build_cores = int(os.environ.get('NIX_LOAD_LIMIT', os.environ.get('NIX_BUILD_CORES', "-1")))


def CPUThreadCount(enable=True):
    if not enable:
        return 1
    else:
        from .GlobalParameters import globalParameters
        cpuThreads = nix_build_cores if nix_build_cores > 0 else globalParameters["CpuThreads"]
        if cpuThreads < 1:
            if os.name == "nt":
                cpuThreads = os.cpu_count()
            else:
                cpuThreads = len(os.sched_getaffinity(0))
        return max(1, min(cpuThreads, 64))


def OverwriteGlobalParameters(newGlobalParameters):
    from . import GlobalParameters

    GlobalParameters.globalParameters.clear()
    GlobalParameters.globalParameters.update(newGlobalParameters)


def pcallWithGlobalParamsMultiArg(f, args, newGlobalParameters):
    OverwriteGlobalParameters(newGlobalParameters)
    return f(*args)


def pcallWithGlobalParamsSingleArg(f, arg, newGlobalParameters):
    OverwriteGlobalParameters(newGlobalParameters)
    return f(arg)


def worker_function(args, function, multiArg):
    """Worker function that executes in the pool process."""
    try:
        if multiArg:
            return function(*args)
        else:
            return function(args)
    except Exception:
        import traceback
        traceback.print_exc()
        raise
    finally:
        sys.stdout.flush()
        sys.stderr.flush()


def progress_logger(iterable, total, message, min_log_interval=5.0):
    """
    Generator that wraps an iterable and logs progress with time-based throttling.

    Only logs progress if at least min_log_interval seconds have passed since last log.
    Only prints completion message if task took >= min_log_interval seconds.

    Yields (index, item) tuples.
    """
    start_time = time.time()
    last_log_time = start_time
    log_interval = 1 + (total // 100)

    for idx, item in enumerate(iterable):
        if idx % log_interval == 0:
            current_time = time.time()
            if (current_time - last_log_time) >= min_log_interval:
                print(f"{message}\t{idx+1: 5d}/{total: 5d}")
                last_log_time = current_time
        yield idx, item

    elapsed = time.time() - start_time
    final_idx = idx + 1 if 'idx' in locals() else 0

    # Only print completion message if task took >= min_log_interval or we logged progress
    if elapsed >= min_log_interval or last_log_time > start_time:
        print(f"\n{message} done!\t{final_idx: 5d}/{total: 5d}")


def imap_with_progress(pool, func, iterable, total, message, chunksize):
    results = []
    for _, result in progress_logger(pool.imap(func, iterable, chunksize=chunksize), total, message):
        results.append(result)
    return results


def _with_idx(func, parts):
    idx, obj = parts
    return idx, func(obj)


def imap_with_progress2(pool, func, iterable, total, message):
    results = [None] * total
    fn = partial(_with_idx, func)

    for _, result in progress_logger(
        pool.imap_unordered(fn, enumerate(iterable), chunksize=max(1, total // 2500)),
        total,
        message
    ):
        orig_idx, item_result = result
        results[orig_idx] = item_result

    return results


def _ParallelMap_generator(worker, objects, objLen, message, chunksize, threadCount, globalParameters):
    """Generator mode for ParallelMap - separated to avoid making entire function a generator."""
    ctx = multiprocessing.get_context('forkserver' if os.name != 'nt' else 'spawn')

    with ctx.Pool(processes=threadCount, maxtasksperchild=1024,
                  initializer=OverwriteGlobalParameters, initargs=(globalParameters,)) as pool:
        for _, result in progress_logger(pool.imap_unordered(worker, objects, chunksize=chunksize), objLen, message):
            yield result


def ParallelMap(
    function: Callable,
    objects: Any,
    message: str = "",
    enable: bool = True,
    multiArg: bool = True,
    minChunkSize: int = 1,
    return_as: str = "list"
):
    """Executes a function over a list of objects in parallel or sequentially.

    This function is generally equivalent to ``list(map(function, objects))``. However, it provides
    additional functionality to run in parallel, depending on the 'enable' flag and available CPU
    threads.

    Args:
        function: The function to apply to each item in 'objects'. If 'multiArg' is True, 'function'
                  should accept multiple arguments.
        objects: An iterable of objects to be processed by 'function'. If 'multiArg' is True, each
                 item in 'objects' should be an iterable of arguments for 'function'.
        message: Optional; a message describing the operation. Default is an empty string.
        enable: Optional; if False, disables parallel execution and runs sequentially. Default is True.
        multiArg: Optional; if True, treats each item in 'objects' as multiple arguments for
                  'function'. Default is True.
        return_as: Optional; "list" (default) or "generator_unordered" for streaming results

    Returns:
        A list or generator containing the results of applying **function** to each item in **objects**.
    """
    from .GlobalParameters import globalParameters

    threadCount = CPUThreadCount(enable)

    if not hasattr(objects, "__len__"):
        objects = list(objects)

    objLen = len(objects)
    if objLen == 0:
        return [] if return_as == "list" else iter([])

    f = (lambda x: function(*x)) if multiArg else function
    if objLen == 1:
        print(f"{message}: (1 task)")
        result = [f(x) for x in objects]
        return result if return_as == "list" else iter(result)

    extra_message = (
        f": {threadCount} thread(s)" + f", {objLen} tasks"
        if objLen
        else ""
    )

    print(f"\nParallelMap {message}{extra_message}\n")

    if threadCount <= 1:
        result = [f(x) for x in objects]
        return result if return_as == "list" else iter(result)

    chunksize = max(minChunkSize, objLen // 2000)
    worker = partial(worker_function, function=function, multiArg=multiArg)

    # Generator mode - yield results as they complete without buffering
    if return_as == "generator_unordered":
        return _ParallelMap_generator(worker, objects, objLen, message, chunksize, threadCount, globalParameters)
    else:
        # List mode - buffer all results
        ctx = multiprocessing.get_context('forkserver' if os.name != 'nt' else 'spawn')
        with ctx.Pool(processes=threadCount, maxtasksperchild=1024,
                      initializer=OverwriteGlobalParameters, initargs=(globalParameters,)) as pool:
            start_time = time.time()
            result = list(imap_with_progress(pool, worker, objects, objLen, message, chunksize))
            elapsed = time.time() - start_time
            print(f"Total time: {elapsed:.1f}s")
            return result


# Compat with old code that used ParallelMap2
ParallelMap2 = ParallelMap
ParallelMapReturnAsGenerator = ParallelMap
