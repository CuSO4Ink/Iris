# Bifrost Roadmap

> 当前处于技术验收期，不做场景。逐项标准见 `TECH-VALIDATION.md`。

## R0：TechLab 与证据模板

建立独立测试关卡、固定相机、统一曝光、开关控制、截图和 GPU 记录方式。

## R1：底层 renderer 验收

完成 T1 恒星光照链、T2 GaussianVolume renderer、T8 FluidFlux、T9 环境 LookDev 的独立验收。

## R2：体积系统验收

完成 T3 Gaussian Field Authoring、T5 自定义 Raymarch Core、T6 HPVolumeCloud UE 适配、T7 Layer 2 Marching Cubes。每项各有独立 demo 和性能边界。

## R3：神经系统验收

完成 T4：训练、ONNX 导入、UE NNE 推理、Gaussian primitive 残差驱动与三组对比。

## R4：技术选型与场景集成决策

所有验收卡结束后，评估哪些模块真正有画面/性能价值，再选少量模块进入最终固定镜头。此时才重新讨论 S3、资产与构图。
