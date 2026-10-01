= Notes 

== Edge detection eval 

- BOOM 1.5 times faster than Rocket due to out of order nature and dynamic scheduling at identical 1 width size
- L1 Data Cache Size vs. Miss Count: L1 D capacity strongly correlates with cache miss reduction (r= -0.9135). Expanding L1 D from 16 KiB to 64 KiB eliminates ~85-95% of misses, but has negligible effect on runtime (r = -0.1636) due to the compute-bound nature of the kernel.
- Removing L2 has a very negative effect on the Rocket Core (+4,398 cycles) due to in-order stall latency, 
BOOM hides DRAM latency via MSHRs and dynamic scheduling.
- Edge detection runs better on an out-of-order architerctive (BOOM) than an in-order one (rocket) due to dense, regular instruction-level-parallelism.
- The larger the cache is, the smaller the cache misses (due to image fitting better) -> need larger images to really compare
