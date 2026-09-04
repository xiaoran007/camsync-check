# Image Input Example

`capture-b0267.json` describes saved 5120 × 800 composite images as four camera views. Paths are fictional and images are not distributed. The schema, protocol, and CLI are draft designs, not an executable checker.

For independent camera images, assign separate sources with ordered frame lists and omit `crop_xywh` to use each full image. Distinct `node_id` values describe multiple acquisition nodes without requiring any acquisition service from this repository.

Exposure is unknown in the example. Supply actual exposure and provenance after acquisition, or let a future decoder estimate it only when identifiable. Two frames illustrate structure; meaningful jitter and drift analysis requires a longer sequence.

The `sweep96-v0` protocol is a phase prototype and cannot guarantee detection of whole-cycle or whole-frame offsets. See the [data contract](../docs/protocol.md).
