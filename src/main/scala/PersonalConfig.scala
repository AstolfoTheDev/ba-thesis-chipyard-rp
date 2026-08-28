package chipyard

import org.chipsalliance.cde.config.{Config}
import freechips.rocketchip.prci.{AsynchronousCrossing}
import freechips.rocketchip.subsystem.{InCluster}

//import barf._ // needed for the prefetchers

// TODO: rename the chips

/*
class chip1 extends Config (
  new barf.WithHellaCachePrefetcher(Seq(0,1,2,3), barf.SingleStridedPrefetcherParams()) ++ // seq(0) targets the first core 
  new freechips.rocketchip.rocket.WithL1DCacheNonblocking(nMSHRs = 4) ++ // needed to handle prefetch misses 

  new freechips.rocketchip.subsystem.WithoutTLMonitors ++ // sppeds up the simulation massively
  new chipyard.config.WithSystemBusWidth(128) ++
  //new chipyard.example.WithInitZero(0x88000000L, 0x1000L) ++   // add InitZero
  //new fftgenerator.WithFFTGenerator(numPoints = 8, width = 16, decPt = 8) ++ // add 8-point mmio fft at the default addr   (0x2400) with 16bit fixed-point numbers.
  new chipyard.example.WithStreamingPassthrough ++          // use top with tilelink-controlled streaming passthrough
  new chipyard.example.WithStreamingFIR ++ 

  new chipyard.config.WithUART(address = 0x10050000, baudrate = 115200) ++ // if using 0x10020000, gets the overlapping memory error || NOTE: other IO options like GPIO and SPI are also possible
  //new chipyard.config.WithUARTAdapter ++ // is this needed?
  new chipyard.config.WithL2TLBs(1024) ++ // 1024 entry sized Translation lookaside buffer
  new freechips.rocketchip.subsystem.WithNMemoryChannels(4) ++ // || HAS TO BE A POWER OF 2
  new freechips.rocketchip.subsystem.WithNBanks(4) ++ // adds 4 parallel, address-interleaved bank || HAS TO BE A POWER OF 2 
  new freechips.rocketchip.subsystem.WithInclusiveCache(capacityKB = 2048, nWays = 16) ++ // SiFive L2 Inclusive cache
  new freechips.rocketchip.rocket.WithNBigCores(2) ++  // ad 2 rocket cores
  new boom.v3.common.WithNLargeBooms(2) ++             // add 2 boom cores
  new chipyard.config.AbstractConfig
  )

class chip2 extends Config (
  //new freechips.rocketchip.subsystem.WithoutTLMonitors ++ // sppeds up the simulation massively
  new chipyard.config.WithUART(address = 0x54000000, baudrate = 115200) ++ // if using 0x10020000, gets the overlapping memory error || NOTE: other IO options like GPIO and SPI are also possible
  new freechips.rocketchip.rocket.WithNBigCores(1) ++  // ad 2 rocket cores
  new chipyard.config.AbstractConfig
  )


// ========== Single Cores ======================

// ========= Rocket Cores =====================

class chip001 extends Config(
  new freechips.rocketchip.rocket.WithNSmallCores(1) ++  
  new chipyard.config.AbstractConfig
  )

class chip002 extends Config(
  new freechips.rocketchip.rocket.WithNBigCores(1) ++ 
  new chipyard.config.AbstractConfig
  )

class chip003 extends Config(
  new freechips.rocketchip.rocket.WithNHugeCores(1) ++  // 1 Rocket Core
  new chipyard.config.AbstractConfig
)

// ========= BOOM Cores =====================

// ========= BOOM V3 Cores ==================


class chip001 extends Config(
  new boom.v3.common.WithNSmallBooms(1) ++   
  new chipyard.config.AbstractConfig
  )

class MediumBoomV3Config extends Config(
  new boom.v3.common.WithNMediumBooms(1) ++                         // medium boom config
  new chipyard.config.AbstractConfig)

class LargeBoomV3Config extends Config(
  new boom.v3.common.WithNLargeBooms(1) ++                          // large boom config
  new chipyard.config.AbstractConfig)

class MegaBoomV3Config extends Config(
  new boom.v3.common.WithNMegaBooms(1) ++                           // mega boom config
  new chipyard.config.AbstractConfig)

// ========= BOOM V4 Cores ==================

class chip001 extends Config(
  new boom.v4.common.WithNSmallBooms(1) ++   
  new chipyard.config.AbstractConfig
  )

class MediumBoomV3Config extends Config(
  new boom.v4.common.WithNMediumBooms(1) ++                         // medium boom config
  new chipyard.config.AbstractConfig)

class LargeBoomV3Config extends Config(
  new boom.v4.common.WithNLargeBooms(1) ++                          // large boom config
  new chipyard.config.AbstractConfig)

class MegaBoomV3Config extends Config(
  new boom.v4.common.WithNMegaBooms(1) ++                           // mega boom config
  new chipyard.config.AbstractConfig)

// ============= Multi Cores ========================

// =========== Homogenous Multi Cores ==============

class chip001 extends Config(
  new freechips.rocketchip.rocket.WithNSmallCores(2) ++    // Add a small "control" core
  new chipyard.config.AbstractConfig
  )

class chip002 extends Config(
  new freechips.rocketchip.rocket.WithNBigCores(2) ++    // Add a small "control" core
  new chipyard.config.AbstractConfig
  )

class chip003 extends Config(
  new freechips.rocketchip.rocket.WithNHugeCores(2) ++  // 1 Rocket Core
  new chipyard.config.AbstractConfig
)


// ========== Hetero Multi Cores =====================

// ========== With BOOM V3 ========================

class chip003 extends Config(
  new freechips.rocketchip.rocket.WithNHugeCores(1) ++  // 1 Rocket Core
  new boom.v3.common.WithNLargeBooms(1) ++                   // large boom config
  new chipyard.config.AbstractConfig
  )

class chip001 extends Config(
  new boom.v3.common.WithNSmallBooms(1) ++   
  new chipyard.config.AbstractConfig
  )

class MediumBoomV3Config extends Config(
  new boom.v3.common.WithNMediumBooms(1) ++                         // medium boom config
  new chipyard.config.AbstractConfig)

class LargeBoomV3Config extends Config(
  new boom.v3.common.WithNLargeBooms(1) ++                          // large boom config
  new chipyard.config.AbstractConfig)

class MegaBoomV3Config extends Config(
  new boom.v3.common.WithNMegaBooms(1) ++                           // mega boom config
  new chipyard.config.AbstractConfig)


// ========== With BOOM V4 ========================

class chip003 extends Config(
  new freechips.rocketchip.rocket.WithNHugeCores(1) ++  // 1 Rocket Core
  new boom.v4.common.WithNLargeBooms(1) ++                   // large boom config
  new chipyard.config.AbstractConfig
  )

class chip001 extends Config(
  new boom.v4.common.WithNSmallBooms(1) ++   
  new chipyard.config.AbstractConfig
  )

class MediumBoomV3Config extends Config(
  new boom.v4.common.WithNMediumBooms(1) ++                         // medium boom config
  new chipyard.config.AbstractConfig)

class LargeBoomV3Config extends Config(
  new boom.v4.common.WithNLargeBooms(1) ++                          // large boom config
  new chipyard.config.AbstractConfig)

class MegaBoomV3Config extends Config(
  new boom.v4.common.WithNMegaBooms(1) ++                           // mega boom config
  new chipyard.config.AbstractConfig)

*/ 

class RocketConfigWithHPM extends Config(
  new chipyard.config.WithNPerfCounters(29) ++
  new freechips.rocketchip.rocket.WithNHugeCores(1) ++
  new chipyard.config.AbstractConfig)

class OwnMemoryRocketConfig extends Config(
  new freechips.rocketchip.subsystem.WithoutTLMonitors ++
  new freechips.rocketchip.subsystem.WithExtMemSize((1<<30) * 1L) ++ // 1GB DRAM
  new freechips.rocketchip.rocket.WithNHugeCores(4) ++
  new freechips.rocketchip.subsystem.WithNMemoryChannels(4) ++
  new chipyard.config.AbstractConfig)
