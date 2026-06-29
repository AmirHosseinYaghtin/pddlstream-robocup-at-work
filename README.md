# RoboCup PDDLStream

Development and Evaluation of Sampling-Based Approaches for Integrated Symbolic and Geometric Planning for Industrial Robots using **PDDLStream**.

This repository contains the implementation developed as part of a Bachelor's thesis. The project applies the original PDDLStream framework to industrial manipulation tasks inspired by the **RoboCup @Work** competition, beginning with a simplified discrete 2D environment and progressively extending toward continuous and full 3D task and motion planning.

The goal of this project is **not** to modify the PDDLStream algorithm itself, but to develop new planning domains, streams, and benchmark tasks for evaluating integrated symbolic and geometric planning in industrial robotics.

---

## Project Objectives

- Implement RoboCup @Work-inspired manipulation tasks using PDDLStream.
- Evaluate the performance of sampling-based task and motion planning.
- Begin with a discrete symbolic world.
- Extend the implementation to continuous geometric planning.
- Eventually support full 3D robotic manipulation.

---

## Repository Structure

```text
robocup-pddlstream/

├── README.md
├── requirements.txt
│
├── pddlstream/              # Original PDDLStream framework
│
├── examples/               # Unmodified reference example(s)
│   ├── discrete_tamp/
│   └── continuous_tamp/
│
├── domains/
│   ├── discrete2d/
│   │   ├── domain.pddl
│   │   ├── stream.pddl
│   │   ├── primitives.py
│   │   ├── run.py
│   │   ├── viewer.py
│   │   └── problems/
│   │
│   ├── continuous2d/
│   │   └── ...
│   │
│   └── full3d/
│       └── ...
│
├── evaluation/
│   ├── benchmark.py
│   ├── results/
│   └── plots.py
│
└── docs/
```

---

## Development Roadmap

### Phase 1 — Discrete 2D

The robot operates in a symbolic world consisting of:

- Tables
- Shelves
- Partitions
- Objects
- Pick
- Place
- Move

No geometric reasoning is performed in this phase. Streams may return predefined symbolic values to validate the planning architecture.

Example tasks:

- Pick and place
- Object transport
- Shelf manipulation
- Precision placement
- Obstacle rearrangement

---

### Phase 2 — Continuous 2D

Replace symbolic locations with continuous poses.

Introduce streams for:

- Grasp generation
- Placement sampling
- Motion planning

The symbolic planner remains unchanged while streams perform geometric reasoning.

---

### Phase 3 — Full 3D

Extend the system to realistic robotic manipulation.

Potential additions include:

- Collision checking
- Robot kinematics
- Motion planning
- Simulation (e.g., PyBullet or Gazebo)
- ROS2 integration

---

## Reference Example (examples)

The `examples/` directory contains an unmodified example from the official PDDLStream repository.

Its purpose is to verify that:

- PDDLStream is installed correctly
- Fast Downward is configured correctly
- The planning framework is functioning before modifying or extending the implementation

---

## RoboCup @Work Tasks

The implemented benchmark problems are inspired by industrial manipulation tasks such as:

- Pick and place
- Object transportation
- Shelf manipulation
- Precision placement
- Blocked object retrieval
- Rearrangement

These tasks are simplified for the discrete environment before being extended to geometric planning.

---

## Evaluation

The implementation will be evaluated using metrics such as:

- Planning time
- Plan length
- Number of stream evaluations
- Number of generated skeletons
- Success rate
- Comparison between planning algorithms (e.g., Adaptive, Focused)

---

## Requirements

- Python 3.10+
- Fast Downward
- PDDLStream
- Additional dependencies listed in `requirements.txt`

---

## Running

To execute the reference example:

```bash
python reference/discrete_tamp/run.py
```

To execute the discrete RoboCup domain:

```bash
python domains/discrete2d/run.py
```

---

## Thesis

**Title**

> Development and Evaluation of Sampling-Based Approaches for Integrated Symbolic and Geometric Planning for Industrial Robots

Bachelor's Thesis

---

## Acknowledgements

This project builds upon the original **PDDLStream** framework developed by Caelan Garrett and collaborators. The implementation in this repository focuses on applying the framework to RoboCup @Work-inspired industrial manipulation tasks and evaluating its performance in progressively more realistic planning environments.
