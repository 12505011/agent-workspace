# MapTR 输出话题约定

用户于 2026-10-13 确认：`maptr_pointcloud` 使用以下固定二进制结构。
发布实现已提交到 perception_q 的 `release-test-mapod-jk-test-1013`，
提交 `67395a440`，已 push。结构布局测试通过；接收端适配及完整播放验证另行执行。

```cpp
struct alignas(16) MapTRPoint {
  float x = 0.0F;
  float y = 0.0F;
  float z = 0.0F;
  std::uint8_t category = 0U;
  std::uint8_t score_q = 0U;
  std::uint16_t instance_id = 0U;
  std::uint16_t point_index = 0U;
  std::array<std::uint8_t, 14> extension{};
};
```

| 字段 | 字节偏移 | PointField 类型 | count |
| --- | ---: | --- | ---: |
| x | 0 | FLOAT32 (7) | 1 |
| y | 4 | FLOAT32 (7) | 1 |
| z | 8 | FLOAT32 (7) | 1 |
| category | 12 | UINT8 (2) | 1 |
| score_q | 13 | UINT8 (2) | 1 |
| instance_id | 14 | UINT16 (4) | 1 |
| point_index | 16 | UINT16 (4) | 1 |
| extension | 18 | UINT8 (2) | 14 |

- `sizeof(MapTRPoint)=32`，`alignof(MapTRPoint)=16`；`point_step=32`。
- `height=1`，`row_step=width*32`；当前输出小端。
- `score_q=round(clamp(score,0,1)*255)`，NaN 置零；接收端按 `score_q/255.0` 解码。
- `category` 保持发布端类别编号，不擅自重排。
- `instance_id` 为当前帧实例序号；`point_index` 为实例内点序号，不是跨帧跟踪 ID。
- 扩展区 18～31 字节全部置零。当前二维 MAP 输出 z=0。
- header 沿用输入点云；此次修改不改变坐标变换或坐标系约定。
- 原有 `intensity/rgb/score` 字段不再属于原始话题格式。可视化端自行按 category 配色。

## 已确认需要适配的接收端

`/data/baize/baize-welldriver/runqfile/maptr_pointcloud_to_vis_ros2.py`
（容器内 `/debug/runqfile/maptr_pointcloud_to_vis_ros2.py`）当前要求
`intensity/rgb` FLOAT32，且将实例和点序号按 UINT32 解码，不能直接读取新格式。
应改为读取 category/score_q UINT8 和 instance_id/point_index UINT16；
其用于显示的派生点云可以保留 intensity/rgb，不能与原始接口混淆。

2026-10-13 已适配上述本地脚本：严格验证32字节字段布局，按 UINT16
读取实例/点序号，按 category 生成显示颜色；显示输出话题仍为
`/maptr_pointcloud_vis`，仅显示用 intensity/rgb 保留。score_q 不作为显示筛选条件。
无 ROS 依赖的合成输入检查通过：大小端、编号500、点排序、插值、旧布局拒绝
和语法检查；真实 ROS2 播放由用户执行，尚未验证。
