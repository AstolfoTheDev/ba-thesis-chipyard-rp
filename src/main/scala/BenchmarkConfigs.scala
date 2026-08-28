package chipyard

import org.chipsalliance.cde.config.{Config}
import freechips.rocketchip.subsystem._
import freechips.rocketchip.rocket._
import freechips.rocketchip.tile._

// ============================================================================
// Custom Cache Mixins for Benchmarking
// ============================================================================

/** Override L1 Data Cache number of sets across Rocket and BOOM tiles */
class WithL1DCacheSets(sets: Int) extends Config((site, here, up) => {
  case TilesLocated(InSubsystem) => up(TilesLocated(InSubsystem)) map {
    case tp: RocketTileAttachParams => tp.copy(tileParams = tp.tileParams.copy(
      dcache = tp.tileParams.dcache.map(_.copy(nSets = sets))))
    case tp: boom.v3.common.BoomTileAttachParams => tp.copy(tileParams = tp.tileParams.copy(
      dcache = tp.tileParams.dcache.map(_.copy(nSets = sets))))
    case tp: boom.v4.common.BoomTileAttachParams => tp.copy(tileParams = tp.tileParams.copy(
      dcache = tp.tileParams.dcache.map(_.copy(nSets = sets))))
    case other => other
  }
})

/** Override L1 Data Cache number of ways across Rocket and BOOM tiles */
class WithL1DCacheWays(ways: Int) extends Config((site, here, up) => {
  case TilesLocated(InSubsystem) => up(TilesLocated(InSubsystem)) map {
    case tp: RocketTileAttachParams => tp.copy(tileParams = tp.tileParams.copy(
      dcache = tp.tileParams.dcache.map(_.copy(nWays = ways))))
    case tp: boom.v3.common.BoomTileAttachParams => tp.copy(tileParams = tp.tileParams.copy(
      dcache = tp.tileParams.dcache.map(_.copy(nWays = ways))))
    case tp: boom.v4.common.BoomTileAttachParams => tp.copy(tileParams = tp.tileParams.copy(
      dcache = tp.tileParams.dcache.map(_.copy(nWays = ways))))
    case other => other
  }
})

/** Convenience mixin to configure L1 Data Cache size (sets and ways) */
class WithL1DCacheSize(sets: Int, ways: Int) extends Config(
  new WithL1DCacheSets(sets) ++
  new WithL1DCacheWays(ways)
)

/** Convenience mixin to set integrated L2 (Inclusive) Cache size and ways */
class WithL2Cache(capacityKB: Int, ways: Int = 8) extends freechips.rocketchip.subsystem.WithInclusiveCache(
  capacityKB = capacityKB,
  nWays = ways
)

// ============================================================================
// 1. Single-Issue Rocket Core Configurations
// ============================================================================

/** Baseline 1-issue Rocket Core with Hardware Performance Counters */
class BenchmarkRocketConfig extends Config(
  new chipyard.config.WithNPerfCounters(29) ++
  new freechips.rocketchip.rocket.WithNBigCores(1) ++
  new chipyard.config.AbstractConfig
)

/** Rocket Core - No L2 Cache (L1 D$ only) */
class BenchmarkRocketNoL2Config extends Config(
  new freechips.rocketchip.subsystem.WithNBanks(0) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new freechips.rocketchip.rocket.WithNBigCores(1) ++
  new chipyard.config.AbstractConfig
)

/** Rocket Core - Small L1 D$ (16 KiB: 64 sets, 4 ways), 512 KiB L2 */
class BenchmarkRocketSmallL1Config extends Config(
  new WithL1DCacheSize(sets = 64, ways = 4) ++
  new WithL2Cache(capacityKB = 512, ways = 8) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new freechips.rocketchip.rocket.WithNBigCores(1) ++
  new chipyard.config.AbstractConfig
)

/** Rocket Core - Medium L1 D$ (32 KiB: 64 sets, 8 ways), 512 KiB L2 */
class BenchmarkRocketMedL1Config extends Config(
  new WithL1DCacheSize(sets = 64, ways = 8) ++
  new WithL2Cache(capacityKB = 512, ways = 8) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new freechips.rocketchip.rocket.WithNBigCores(1) ++
  new chipyard.config.AbstractConfig
)

/** Rocket Core - Large L1 D$ (64 KiB: 128 sets, 8 ways), 512 KiB L2 */
class BenchmarkRocketLargeL1Config extends Config(
  new WithL1DCacheSize(sets = 128, ways = 8) ++
  new WithL2Cache(capacityKB = 512, ways = 8) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new freechips.rocketchip.rocket.WithNBigCores(1) ++
  new chipyard.config.AbstractConfig
)

/** Rocket Core - Medium L1 D$ (32 KiB), Large 2 MiB (2048 KiB) L2 */
class BenchmarkRocketLargeL2Config extends Config(
  new WithL1DCacheSize(sets = 64, ways = 8) ++
  new WithL2Cache(capacityKB = 2048, ways = 16) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new freechips.rocketchip.rocket.WithNBigCores(1) ++
  new chipyard.config.AbstractConfig
)

// ============================================================================
// 2. Single-Issue Small BOOM Core Configurations
// ============================================================================

/** Baseline 1-wide Small BOOM Core with Hardware Performance Counters */
class BenchmarkSmallBoomConfig extends Config(
  new chipyard.config.WithNPerfCounters(29) ++
  new boom.v3.common.WithNSmallBooms(1) ++
  new chipyard.config.AbstractConfig
)

/** Small BOOM Core - No L2 Cache */
class BenchmarkSmallBoomNoL2Config extends Config(
  new freechips.rocketchip.subsystem.WithNBanks(0) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new boom.v3.common.WithNSmallBooms(1) ++
  new chipyard.config.AbstractConfig
)

/** Small BOOM Core - Small L1 D$ (16 KiB: 64 sets, 4 ways), 512 KiB L2 */
class BenchmarkSmallBoomSmallL1Config extends Config(
  new WithL1DCacheSize(sets = 64, ways = 4) ++
  new WithL2Cache(capacityKB = 512, ways = 8) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new boom.v3.common.WithNSmallBooms(1) ++
  new chipyard.config.AbstractConfig
)

/** Small BOOM Core - Medium L1 D$ (32 KiB: 64 sets, 8 ways), 512 KiB L2 */
class BenchmarkSmallBoomMedL1Config extends Config(
  new WithL1DCacheSize(sets = 64, ways = 8) ++
  new WithL2Cache(capacityKB = 512, ways = 8) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new boom.v3.common.WithNSmallBooms(1) ++
  new chipyard.config.AbstractConfig
)

/** Small BOOM Core - Large L1 D$ (64 KiB: 128 sets, 8 ways), 512 KiB L2 */
class BenchmarkSmallBoomLargeL1Config extends Config(
  new WithL1DCacheSize(sets = 128, ways = 8) ++
  new WithL2Cache(capacityKB = 512, ways = 8) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new boom.v3.common.WithNSmallBooms(1) ++
  new chipyard.config.AbstractConfig
)

/** Small BOOM Core - Medium L1 D$ (32 KiB), Large 2 MiB (2048 KiB) L2 */
class BenchmarkSmallBoomLargeL2Config extends Config(
  new WithL1DCacheSize(sets = 64, ways = 8) ++
  new WithL2Cache(capacityKB = 2048, ways = 16) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new boom.v3.common.WithNSmallBooms(1) ++
  new chipyard.config.AbstractConfig
)

// ============================================================================
// 3. 2-Wide Medium BOOM Core Configurations
// ============================================================================

/** Baseline 2-wide Medium BOOM Core with Hardware Performance Counters */
class BenchmarkMediumBoomConfig extends Config(
  new chipyard.config.WithNPerfCounters(29) ++
  new boom.v3.common.WithNMediumBooms(1) ++
  new chipyard.config.AbstractConfig
)

/** Medium BOOM Core - No L2 Cache */
class BenchmarkMediumBoomNoL2Config extends Config(
  new freechips.rocketchip.subsystem.WithNBanks(0) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new boom.v3.common.WithNMediumBooms(1) ++
  new chipyard.config.AbstractConfig
)

/** Medium BOOM Core - Small L1 D$ (16 KiB: 64 sets, 4 ways), 512 KiB L2 */
class BenchmarkMediumBoomSmallL1Config extends Config(
  new WithL1DCacheSize(sets = 64, ways = 4) ++
  new WithL2Cache(capacityKB = 512, ways = 8) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new boom.v3.common.WithNMediumBooms(1) ++
  new chipyard.config.AbstractConfig
)

/** Medium BOOM Core - Medium L1 D$ (32 KiB: 64 sets, 8 ways), 512 KiB L2 */
class BenchmarkMediumBoomMedL1Config extends Config(
  new WithL1DCacheSize(sets = 64, ways = 8) ++
  new WithL2Cache(capacityKB = 512, ways = 8) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new boom.v3.common.WithNMediumBooms(1) ++
  new chipyard.config.AbstractConfig
)

/** Medium BOOM Core - Large L1 D$ (64 KiB: 128 sets, 8 ways), 512 KiB L2 */
class BenchmarkMediumBoomLargeL1Config extends Config(
  new WithL1DCacheSize(sets = 128, ways = 8) ++
  new WithL2Cache(capacityKB = 512, ways = 8) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new boom.v3.common.WithNMediumBooms(1) ++
  new chipyard.config.AbstractConfig
)

/** Medium BOOM Core - Medium L1 D$ (32 KiB), Large 2 MiB (2048 KiB) L2 */
class BenchmarkMediumBoomLargeL2Config extends Config(
  new WithL1DCacheSize(sets = 64, ways = 8) ++
  new WithL2Cache(capacityKB = 2048, ways = 16) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new boom.v3.common.WithNMediumBooms(1) ++
  new chipyard.config.AbstractConfig
)

// ============================================================================
// 4. 3-Wide Large BOOM Core Configurations
// ============================================================================

/** Baseline 3-wide Large BOOM Core with Hardware Performance Counters */
class BenchmarkLargeBoomConfig extends Config(
  new chipyard.config.WithNPerfCounters(29) ++
  new boom.v3.common.WithNLargeBooms(1) ++
  new chipyard.config.WithSystemBusWidth(128) ++
  new chipyard.config.AbstractConfig
)

/** Large BOOM Core - No L2 Cache */
class BenchmarkLargeBoomNoL2Config extends Config(
  new freechips.rocketchip.subsystem.WithNBanks(0) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new boom.v3.common.WithNLargeBooms(1) ++
  new chipyard.config.WithSystemBusWidth(128) ++
  new chipyard.config.AbstractConfig
)

/** Large BOOM Core - Small L1 D$ (16 KiB: 64 sets, 4 ways), 512 KiB L2 */
class BenchmarkLargeBoomSmallL1Config extends Config(
  new WithL1DCacheSize(sets = 64, ways = 4) ++
  new WithL2Cache(capacityKB = 512, ways = 8) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new boom.v3.common.WithNLargeBooms(1) ++
  new chipyard.config.WithSystemBusWidth(128) ++
  new chipyard.config.AbstractConfig
)

/** Large BOOM Core - Medium L1 D$ (32 KiB: 64 sets, 8 ways), 512 KiB L2 */
class BenchmarkLargeBoomMedL1Config extends Config(
  new WithL1DCacheSize(sets = 64, ways = 8) ++
  new WithL2Cache(capacityKB = 512, ways = 8) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new boom.v3.common.WithNLargeBooms(1) ++
  new chipyard.config.WithSystemBusWidth(128) ++
  new chipyard.config.AbstractConfig
)

/** Large BOOM Core - Large L1 D$ (64 KiB: 128 sets, 8 ways), 512 KiB L2 */
class BenchmarkLargeBoomLargeL1Config extends Config(
  new WithL1DCacheSize(sets = 128, ways = 8) ++
  new WithL2Cache(capacityKB = 512, ways = 8) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new boom.v3.common.WithNLargeBooms(1) ++
  new chipyard.config.WithSystemBusWidth(128) ++
  new chipyard.config.AbstractConfig
)

/** Large BOOM Core - Large L1 D$ (64 KiB), Large 2 MiB (2048 KiB) L2 */
class BenchmarkLargeBoomLargeL2Config extends Config(
  new WithL1DCacheSize(sets = 128, ways = 8) ++
  new WithL2Cache(capacityKB = 2048, ways = 16) ++
  new chipyard.config.WithNPerfCounters(29) ++
  new boom.v3.common.WithNLargeBooms(1) ++
  new chipyard.config.WithSystemBusWidth(128) ++
  new chipyard.config.AbstractConfig
)
