/* Runs one benchmark program for run.py and measures it: measure <program> prints, on stderr,
 *   wall_ns <nanoseconds> maxrss <bytes>
 * after the program's own output has gone to stdout. A small launcher, rather than Python, starts the program, so the
 * peak resident set is the program's alone (Linux carries the forking process's peak across exec) and the wall time
 * is posix_spawn to wait4 on CLOCK_MONOTONIC. */
#define _DARWIN_C_SOURCE
#define _GNU_SOURCE
#include <spawn.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <time.h>

extern char **environ;

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: measure <program> [args...]\n");
        return 2;
    }
    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);
    pid_t pid;
    if (posix_spawn(&pid, argv[1], NULL, NULL, argv + 1, environ) != 0) {
        perror("posix_spawn");
        return 2;
    }
    int status;
    struct rusage usage;
    if (wait4(pid, &status, 0, &usage) != pid) {
        perror("wait4");
        return 2;
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    int64_t ns = (int64_t)(end.tv_sec - start.tv_sec) * 1000000000 + (end.tv_nsec - start.tv_nsec);
#if defined(__APPLE__)
    int64_t rss = (int64_t)usage.ru_maxrss;          /* bytes */
#else
    int64_t rss = (int64_t)usage.ru_maxrss * 1024;   /* KiB */
#endif
    fprintf(stderr, "wall_ns %lld maxrss %lld\n", (long long)ns, (long long)rss);
    if (!WIFEXITED(status)) return 3;
    return WEXITSTATUS(status);
}
