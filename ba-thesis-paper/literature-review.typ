= Literature Review

== Outline

   - Evolution of Open-Source ISAs and RISC-V
   - Modern SoC Generator Ecosystems (Chipyard vs. OpenTitan vs. PULP)
   - RISC-V Core Microarchitectures (In-Order Rocket vs. Out-of-Order BOOM)
   - Simulation Frameworks (Software Verilator/QEMU vs. FPGA Emulation)
   - Hardware Deployment & Toolchains on FPGAs (Vivado, Chisel-to-Verilog Pipeline)
   - Embedded Software Architecture (Baremetal Workloads, OpenSBI, and Linux Boot Flow)



Fundamental Chipyard & Core Generator Literature

The Chipyard Framework (Primary Reference)
Citation: Amid, A., Biancolin, D., Gonzalez, A., Grubb, K., Karandikar, S., Liew, H., ... & Asanović, K. (2020). Chipyard: Integrated Agile RISC-V SoC Design Environment. IEEE Micro, 40(4), 35-45.

Why it’s crucial: This is the seminal paper introducing Chipyard. It explains how Rocket Chip, BOOM, Hwacha, and peripheral generators assemble into a cohesive SoC using Chisel and FIRRTL.

Rocket Chip SoC Generator

Citation: Asanović, K., Avizienis, R., Bachrach, J., Beamer, S., Biancolin, D., Celio, C., ... & Waterman, A. (2016). The Rocket Chip Generator. University of California, Berkeley, Tech. Rep. UCB/EECS-2016-17.

Why it’s crucial: Explains tile-based microarchitectures, TileLink interconnects, and parameterized core generation (essential for your single/multicore and heterogeneous setup evaluations).

The BOOM Core (Out-of-Order Execution)

Citation: Celio, C., Chiu, P. F., Nikolic, B., Patterson, D., & Asanović, K. (2015). BOOM: The Berkeley Out-of-Order Machine. University of California, Berkeley, Tech. Rep. UCB/EECS-2015-167.

Why it’s crucial: Useful if you plan to compare simple in-order cores (Rocket) with complex out-of-order execution units (BOOM) in your SoC configurations.


2. FPGA Implementation & Prototyping FrameworksFPGA Acceleration and Prototyping

(FireSim)Citation: Karandikar, S., Mao, H., Kim, D., Biancolin, D., Amid, A., Lee, A., ... & Asanović, K. (2018). FireSim: FPGA-accelerated cycle-exact scale-out system simulation in the public cloud. ISCA 2018.Why it’s crucial: Demonstrates how Chipyard SoCs are targeted to FPGA targets. Even if using a physical board like Xilinx VC707, FireSim’s host-target transformation principles provide theoretical depth for your FPGA mapping sections.RISC-V Soft-Cores on FPGA ArchitecturesCitation: Traber, A., Gautschi, M., Pullini, A., Schiavone, P. D., Rossi, D., & Benini, L. (2016). PULPino: An open-source microcontroller system-on-chip. PATMOS 2016.Why it’s crucial: Excellent comparative paper discussing resource utilization (LUTs, FFs, BRAMs) and maximum operating frequencies ($f_{max}$) when synthesizing RISC-V soft cores on FPGAs.3. Simulation, Software Flow & OS DeploymentSoftware Verification via VerilatorCitation: Snyder, W. (2004). Verilator: Fast open-source C++ HDL simulator.Why it’s crucial: Directly addresses your methodology step involving Verilator-based functional verification prior to FPGA synthesis.Bootstrapping Linux on RISC-V SystemsCitation: Waterman, A., & Asanović, K. (2019). The RISC-V Instruction Set Manual, Volume II: Privileged Architecture. RISC-V Foundation.Why it’s crucial: Explains Machine (M), Supervisor (S), and User (U) privilege modes required for handling baremetal applications vs. rich OS kernels (Linux with SBI/OpenSBI).


.X Comparative Analysis: Chipyard/Chisel Agile Design vs. Traditional Verilog/VHDL Methodologies
2.X.1 The Classical Approach: Verilog and VHDL

Traditional System-on-Chip (SoC) development relies heavily on Hardware Description Languages (HDLs) such as Verilog, SystemVerilog, and VHDL. Developed in the 1980s, these languages were originally designed for modeling and simulating discrete logic circuits rather than generating complex, highly parameterizable, multi-core system architectures.

While conventional HDLs offer fine-grained control over gate-level implementation and register-transfer level (RTL) timing, they present several structural limitations when applied to modern heterogenous SoC design:

    Limited Abstraction & Reusability: Traditional HDLs lack modern software engineering paradigms such as object-oriented programming, parametric polymorphism, and functional metaprogramming. Parameterization in Verilog (defparam / parameter) or VHDL (generic) is often restricted to basic structural values (e.g., bus widths or array depths) and struggle to express complex conditional topologies, such as arbitrary cache hierarchy topologies or dynamic interconnect routing.

    Manual Integration Overhead: In classical workflows, interconnecting processor cores, memory buses (e.g., AXI, AHB), memory management units (MMUs), and peripheral blocks requires manual wiring or rigid, GUI-driven IP integration environments (e.g., AMD Vivado IP Integrator). This process is prone to human error, difficult to version-control, and labor-intensive to refactor across different hardware configurations.

    Verification Bottlenecks: Verification in traditional flows relies on separate hardware verification languages (e.g., SystemVerilog UVM) or C/C++ co-simulation wrappers, creating a disconnect between the design specifications and testbench architectures.

2.X.2 Agile Hardware Design with Chisel

To address the productivity gap in hardware design, Constructing Hardware in a Scala-Embedded Language (Chisel) introduces hardware construction primitives embedded within the high-level Scala programming language. Chisel does not compile directly to gates; instead, it acts as a metaprogramming language that executes Scala code to generate an intermediate representation known as FIRRTL (Flexible Intermediate Representation for RTL), which is subsequently lowered into structural Verilog.

Key architectural advantages provided by Chisel include:

    Object-Oriented & Functional Metaprogramming: Designers can leverage abstract classes, traits, and higher-order functions to write hardware design generators rather than static instances. For example, an arbiter or interconnect crossbar can be procedurally generated based on arbitrary Scala data structures evaluated at compile time.

    Type Safety & Object Parametricity: Chisel enforces strict type checking during hardware elaboration. Signals, interfaces, and bundled records (e.g., Decoupled interfaces implementing handshake protocols) are verified prior to Verilog generation, eliminating structural configuration errors early in the design cycle.

    Intermediate Representation (FIRRTL): By decoupling the high-level Chisel specification from the target Verilog, FIRRTL enables automated compilation passes. Transformations—such as clock-gating insertion, memory mapping, or instrumentation for FPGA emulation—can be applied programmatically to the FIRRTL AST (Abstract Syntax Tree) without modifying the source design.

2.X.3 Integrated Ecosystem: The Chipyard Framework

While Chisel provides the design language, Chipyard provides the integrated agile SoC development framework. Chipyard combines a suite of Chisel-based core generators—such as the in-order Rocket core and the out-of-order BOOM (Berkeley Out-of-Order Machine)—alongside TileLink interconnect generators, memory controllers, and peripheral devices into a unified, version-controlled repository.

Compared to traditional Verilog IP integration workflows, Chipyard provides a fundamentally different paradigm:
Dimension	Traditional Verilog / VHDL Design	Chipyard / Chisel Generator Methodology
Design Abstraction	Register-Transfer Level (RTL) netlists / instances	Metaprogrammed hardware generators in Scala
System Interconnect	Manual wiring of AXI/AHB buses or GUI IP Integrators	Programmatically elaborated TileLink / AXI crossbars
Parameterization	Static macros, localparams, and simple generics	Dynamic Scala-based configuration objects evaluated at elaboration
Target Portability	Manual adaptation per target board or ASIC process	Uniform elaboration targeting C++ simulators (Verilator), FPGAs, or ASIC tools
Verification Cycle	UVM / SystemVerilog testbenches, manual simulation setups	Integrated C++ co-simulation (Verilator), QEMU, and FPGA-accelerated FireSim
2.X.4 Trade-offs and Considerations for FPGA Prototyping

While Chisel and Chipyard dramatically improve design velocity and architecture-level exploration, transitioning from high-level dynamic generators to physical FPGA deployment introduces specific trade-offs:

    Compilation and Elaboration Latency: Chisel designs require a multi-stage compilation flow (Scala elaboration → FIRRTL transformations → Verilog generation → Vivado synthesis). The elaboration stage can consume significant memory and CPU time for large, heterogeneous multi-core configurations.

    Readability of Generated RTL: The Verilog emitted by the Chisel compiler is machine-generated structural netlist code. While fully functional and synth-ready, debugging post-synthesis timing closure issues or signal routing at the generated Verilog level can be significantly more challenging than in hand-written Verilog.

    Resource Utilization Optimization: Hand-crafted VHDL or Verilog can be micro-optimized for specific FPGA primitives (e.g., direct instantiation of Xilinx DSP48 slices or specialized BRAM configurations). Chisel generators abstract these features away, relying on the FPGA synthesis tool (e.g., Vivado) or specialized memory mapping FIRRTL passes to infer optimal target-specific hardware resources correctly.


3. Methodology & Implementation FlowThis section details the end-to-end operational pipeline used to design, verify, and implement the RISC-V System-on-Chip (SoC). The methodology spans three core phases: setting up the Chipyard environment, software-based simulation using Verilator, and hardware synthesis for the Xilinx VC707 FPGA development board.+-----------------------------------------------------------------------+
|                         3.1 Environment Setup                         |
|   Ubuntu Host + RISC-V GNU Toolchain + Chipyard Repo + Conda/SBT Flow  |
+----------------------------------+------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                    3.2 SoC Configuration & Generation                 |
|      Scala Configs (Rocket/BOOM, Caches, Memory) --> Chisel --> FIRRTL |
+----------------------------------+------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                  3.3 Software Simulation & Verification               |
|      FIRRTL --> Verilator C++ Model --> Baremetal / OpenSBI Tests      |
+----------------------------------+------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                   3.4 FPGA Synthesis & Implementation                 |
|   Verilog Emission --> Vivado Toolchain --> VC707 Bitstream & Boot    |
+-----------------------------------------------------------------------+
3.1 Environment Setup & Toolchain DeploymentDeveloping with Chipyard requires a tightly controlled Linux-based environment to satisfy complex dependencies across Scala, C++ build chains, and electronic design automation (EDA) tools.3.1.1 Host Infrastructure and DependenciesThe primary development environment was configured on an Ubuntu LTS host. Initial preparation involved installing host-level build utilities, including build-essential, gawk, bison, flex, texinfo, libgmp-dev, and zlib1g-dev.3.1.2 Chipyard Framework InstallationChipyard management relies on Conda package environments and Git submodules to maintain strict version consistency across dozens of embedded repositories. The initialization pipeline followed three steps:Repository Acquisition: Cloning the Chipyard framework recursively to fetch submodules including Rocket Chip, BOOM, FireSim, and Chisel compilers.Environment Bootstrapping: Executing build-setup.sh to construct a dedicated Conda environment containing Python tools, Scala Build Tool (sbt), dynamic linkers, and system libraries.Cross-Compiler Construction: Compiling the RISC-V GNU Toolchain (riscv64-unknown-elf-gcc and riscv64-unknown-linux-gnu-gcc) to enable compilation for both baremetal execution (Machine-mode) and Linux OS environments (Supervisor/User-mode).3.2 SoC Architecture ConfigurationThe SoC parameters were defined using Chisel's dynamic configuration system within Chipyard. Rather than modifying raw HDL netlists, hardware configurations are specified as Scala classes inheriting from Config.3.2.1 Target SoC Profile SelectionTo evaluate trade-offs in resource utilization and execution speed, two primary SoC archetypes were constructed:Baseline In-Order Core (Rocket): A single-issue, 5-stage in-order pipeline core (FreeChipsProject.RocketConfig) configured with RV64GC capabilities, hardware multiply/divide, and separate L1 instruction and data caches.High-Performance Out-of-Order Core (BOOM): A superscalar, out-of-order core (BoomConfig) featuring speculative execution, register renaming, and hardware branch prediction to assess performance improvements against baseline in-order execution.3.2.2 Subsystem and Interconnect ElaborationThe core generators were connected to system peripherals via the TileLink interconnect protocol. Memory mapping parameters were configured to establish:On-Chip Memory (SRAM/BootROM): Direct memory mapping for Zero Stage Bootloader (ZSBL) routines.UART and Debug Modules: Standard RISC-V Debug Module (DTM) and 16550-compatible UART controllers for console I/O.External Memory Controller: A TileLink-to-AXI4 converter bridge mapped to the external DDR3 memory address range.3.3 Software Simulation with VerilatorBefore hardware synthesis, functional correctness was verified at the software level. Software simulation accelerates debugging by providing full signal visibility without the long turnaround times of FPGA bitstream compilation.3.3.1 Verilator Compilation FlowChipyard leverages Verilator, an open-source C++ HDL simulator. The hardware generator converts Chisel code to FIRRTL, which is lowered into Verilog. Verilator then compiles the generated Verilog netlist into a cycle-exact, multithreaded C++ executable model.3.3.2 Execution of Baremetal WorkloadsVerification was executed across two distinct software levels:Unit & Microbenchmarks: Compiling test cases from riscv-tests (e.g., ISA tests for rv64ui and rv64uf) to verify instruction decoding, arithmetic correctness, and exception handling.Representative Algorithmic Benchmarks: Executing C-based workloads (e.g., matrix multiplication, AES encryption, and FFT) compiled using riscv64-unknown-elf-gcc. Execution time was recorded via hardware performance counters (rdcycle, rdinstret).3.4 FPGA Synthesis & Implementation (Xilinx VC707)After software verification, the target SoC design was prepared for deployment on the Xilinx Virtex-7 FPGA VC707 Evaluation Kit.+------------------+     +-------------------+     +------------------+
| Chisel Source    | --> | FIRRTL Compiler   | --> | Structural       |
| Configuration    |     | Transformations   |     | Verilog Emission |
+------------------+     +-------------------+     +--------+---------+
                                                            |
                                                            v
+------------------+     +-------------------+     +------------------+
| VC707 Bitstream  | <-- | Vivado Synthesis  | <-- | Top-Level Wrapper|
| (.bit Generation)|     | & Place-and-Route |     | & XDC Constraints|
+------------------+     +-------------------+     +------------------+
3.4.1 Top-Level Wrapper & IP IntegrationThe high-level Chipyard SoC specification must be bridged to the physical interfaces of the VC707 board:Clocking & Resets: A Xilinx Mixed-Mode Clock Manager (MMCM) IP core was integrated to step down the board's differential 200 MHz system clock to a stable operating frequency ($f_{clk}$) for the RISC-V core (e.g., 50 MHz to 100 MHz).DDR3 Memory Controller: The TileLink external memory port was bridged to AMD/Xilinx Memory Interface Generator (MIG) IP to interface with the 1GB DDR3 SODIMM on the VC707 board.Pin Mapping (XDC Constraints): A physical constraint file (.xdc) was mapped to tie top-level SoC signals (UART TX/RX, JTAG, System Clock, Reset) to dedicated VC707 FPGA package pins.3.4.2 Synthesis and Implementation in VivadoThe generated Verilog files and constraint scripts were processed using AMD Vivado:RTL Synthesis: Translating structural Verilog into target-specific FPGA primitives (LUTs, Flip-Flops, DSP48E1 slices, and BRAMs).Implementation (Place & Route): Mapping synthesized logic cells onto physical Virtex-7 Configurable Logic Blocks (CLBs) and optimizing dynamic signal routing paths.Timing Closure Verification: Checking the Setup and Hold Slack against static timing analysis (STA) metrics to ensure zero timing violations at the target clock frequency.Bitstream Generation: Generating the final binary configuration file (.bit).3.4.3 Hardware Flashing & ExecutionThe produced .bit file is loaded onto the VC707 FPGA using the Vivado Hardware Manager over JTAG. Console output is monitored using serial communication utilities (e.g., minicom or picocom) connected to the USB-UART bridge interface.
