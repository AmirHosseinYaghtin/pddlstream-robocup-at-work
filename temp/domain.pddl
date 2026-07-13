(define (domain robocup-continuous-tamp)

  (:requirements :strips :equality :adl :action-costs)

  (:predicates

    ;; ============================================================
    ;; Static / type-guard predicates
    ;; ============================================================

    (Robot ?r)
    (Object ?o)
    (Furniture ?f)          ;; static: floor-level obstacle (table/shelf/box) that
                            ;; blocks the ROBOT BASE only. Deliberately excluded
                            ;; from arm collision checks -- the 2D abstraction
                            ;; assumes the arm operates above furniture height, so
                            ;; only its floor footprint matters, and only for base
                            ;; motion/docking.

    (BaseConf ?q)           ;; a robot base configuration (x, y, theta)
    (ArmConf ?a)            ;; an arm joint configuration
    (BaseTraj ?t)           ;; a continuous base trajectory (RRT path)
    (ArmTraj ?t)            ;; a continuous arm trajectory (RRT path)

    (Pose ?o ?p)            ;; p is a valid placement pose for object o
    (Grasp ?o ?g)           ;; g is a valid grasp transform for object o

    (Region ?reg)           ;; a workspace region (table / shelf / box)
    (Placeable ?o ?p ?reg)  ;; pose p of object o lies inside region reg

    (TraySlot ?s)           ;; one of the (up to 3) tray slots

    ;; ------------------------------------------------------------
    ;; Stream-certified relations
    ;; ------------------------------------------------------------

    (Dock ?o ?p ?bq)                  ;; sample-base-dock: bq is a good base
                                      ;; pose from which to manipulate object
                                      ;; o currently/eventually at pose p

    (IK ?o ?p ?g ?bq ?aq)             ;; solve-ik: aq is a valid arm config
                                      ;; achieving grasp g on object o at
                                      ;; pose p, from base pose bq

    (BaseMotion ?bq1 ?bt ?bq2)        ;; plan-base-motion: bt is a
                                      ;; collision-checked (vs. static map)
                                      ;; RRT path from bq1 to bq2

    (ArmMotionFree ?bq ?aq1 ?at ?aq2) ;; plan-arm-motion, not holding
    (ArmMotionHolding ?bq ?aq1 ?at ?aq2 ?o ?g)
                                      ;; plan-arm-motion while holding
                                      ;; object o with grasp g (different
                                      ;; swept geometry than free motion)

    (BaseCFree ?bt ?o2 ?p2)           ;; collision-free: base traj bt is
                                      ;; collision-free against object o2
                                      ;; parked at pose p2
    (ArmCFree ?bq ?at ?o2 ?p2)        ;; collision-free: arm traj at is
                                      ;; collision-free against object o2
                                      ;; parked at pose p2

    ;; ============================================================
    ;; Fluent predicates
    ;; ============================================================

    (AtBaseConf ?r ?bq)
    (AtArmConf ?r ?aq)
    (AtPose ?o ?p)

    (AtGrasp ?r ?o ?g)      ;; object o is currently held in the gripper
    (HandEmpty ?r)

    (OnTray ?r ?o ?s)       ;; object o is stowed in tray slot s
    (TraySlotFree ?r ?s)

    (CanMoveBase ?r)        ;; gating flags, same role as CanMove /
    (CanMoveArm ?r)         ;; CanManipulate in continuous-tamp: forces
                            ;; move_base -> (pick|place|stow|unstow) ->
                            ;; move_base ... alternation so the planner
                            ;; can't interleave nonsensical action pairs

    ;; ============================================================
    ;; Derived predicates
    ;; ============================================================

    (Holding ?r ?o)         ;; true if o is in the gripper OR on the tray
    (In ?o ?reg)            ;; true if o's current pose lies in region reg
  )

  (:functions
    (Cost)                    ;; fixed per-action cost for pick/place/etc.
    (Dist ?bq1 ?bq2)          ;; base path length between two base confs
    (ArmDist ?aq1 ?aq2)       ;; arm joint-space distance between two confs
    (ExtraBaseCost ?bq1 ?bq2) ;; optional penalty for "unnecessary" base
                              ;; travel, supplied by the same stream that
                              ;; certifies BaseMotion
    (total-cost)
  )

  ;; ============================================================
  ;; move_base : continuous base motion (RRT)
  ;; ============================================================

  (:action move_base
    :parameters (?r ?bq1 ?bt ?bq2)
    :precondition (and
        (Robot ?r)
        (BaseConf ?bq1) (BaseConf ?bq2) (BaseTraj ?bt)
        (BaseMotion ?bq1 ?bt ?bq2)
        (AtBaseConf ?r ?bq1)
        (CanMoveBase ?r)
        (forall (?o2 ?p2)
          (imply (and (or (Object ?o2) (Furniture ?o2)) (Pose ?o2 ?p2) (AtPose ?o2 ?p2))
                 (BaseCFree ?bt ?o2 ?p2)))
    )
    :effect (and
        (AtBaseConf ?r ?bq2)
        (not (AtBaseConf ?r ?bq1))
        (not (CanMoveBase ?r))
        (CanMoveArm ?r)
        (increase (total-cost) (Dist ?bq1 ?bq2))
        (increase (total-cost) (ExtraBaseCost ?bq1 ?bq2))
    )
  )

  ;; ============================================================
  ;; pick : grasp a free object from the environment
  ;; base is assumed stationary and correctly docked; arm sweeps
  ;; out from its home/rest config aq1 to the grasp config aq2
  ;; and (abstracted) retracts back to aq1 carrying the object
  ;; ============================================================

  (:action pick
    :parameters (?r ?o ?p ?g ?bq ?aq1 ?aq2 ?at)
    :precondition (and
        (Robot ?r) (Object ?o)
        (Pose ?o ?p) (Grasp ?o ?g)
        (BaseConf ?bq) (ArmConf ?aq1) (ArmConf ?aq2) (ArmTraj ?at)
        (Dock ?o ?p ?bq)
        (IK ?o ?p ?g ?bq ?aq2)
        (ArmMotionFree ?bq ?aq1 ?at ?aq2)
        (AtBaseConf ?r ?bq)
        (AtArmConf ?r ?aq1)
        (AtPose ?o ?p)
        (HandEmpty ?r)
        (CanMoveArm ?r)
        (forall (?o2 ?p2)
          (imply (and (Object ?o2) (Pose ?o2 ?p2) (AtPose ?o2 ?p2) (not (= ?o2 ?o)))
                 (ArmCFree ?bq ?at ?o2 ?p2)))
    )
    :effect (and
        (AtGrasp ?r ?o ?g)
        (not (AtPose ?o ?p))
        (not (HandEmpty ?r))
        (not (CanMoveArm ?r))
        (CanMoveBase ?r)
        (increase (total-cost) (ArmDist ?aq1 ?aq2))
        (increase (total-cost) (Cost))
    )
  )

  ;; ============================================================
  ;; place : place the currently-gripped object at a target pose
  ;; ============================================================

  (:action place
    :parameters (?r ?o ?p ?g ?bq ?aq1 ?aq2 ?at)
    :precondition (and
        (Robot ?r) (Object ?o)
        (Pose ?o ?p) (Grasp ?o ?g)
        (BaseConf ?bq) (ArmConf ?aq1) (ArmConf ?aq2) (ArmTraj ?at)
        (Dock ?o ?p ?bq)
        (IK ?o ?p ?g ?bq ?aq2)
        (ArmMotionHolding ?bq ?aq1 ?at ?aq2 ?o ?g)
        (AtBaseConf ?r ?bq)
        (AtArmConf ?r ?aq1)
        (AtGrasp ?r ?o ?g)
        (CanMoveArm ?r)
        (forall (?o2 ?p2)
          (imply (and (Object ?o2) (Pose ?o2 ?p2) (AtPose ?o2 ?p2) (not (= ?o2 ?o)))
                 (ArmCFree ?bq ?at ?o2 ?p2)))
    )
    :effect (and
        (AtPose ?o ?p)
        (HandEmpty ?r)
        (not (AtGrasp ?r ?o ?g))
        (not (CanMoveArm ?r))
        (CanMoveBase ?r)
        (increase (total-cost) (ArmDist ?aq1 ?aq2))
        (increase (total-cost) (Cost))
    )
  )

  ;; ============================================================
  ;; stow / unstow : move a held object on/off the tray
  ;; Purely a bookkeeping transfer (arm already holds the object
  ;; from a pick; the tray sits within reach), so no motion stream
  ;; is required -- these are cheap, instantaneous actions that
  ;; let the robot free its gripper to pick up to 2 more objects
  ;; before it must place any of them.
  ;; ============================================================

  (:action stow
    :parameters (?r ?o ?g ?s)
    :precondition (and
        (Robot ?r) (Object ?o) (Grasp ?o ?g) (TraySlot ?s)
        (AtGrasp ?r ?o ?g)
        (TraySlotFree ?r ?s)
    )
    :effect (and
        (OnTray ?r ?o ?s)
        (HandEmpty ?r)
        (not (TraySlotFree ?r ?s))
        (not (AtGrasp ?r ?o ?g))
        (increase (total-cost) (Cost))
    )
  )

  (:action unstow
    :parameters (?r ?o ?g ?s)
    :precondition (and
        (Robot ?r) (Object ?o) (Grasp ?o ?g) (TraySlot ?s)
        (OnTray ?r ?o ?s)
        (HandEmpty ?r)
    )
    :effect (and
        (AtGrasp ?r ?o ?g)
        (TraySlotFree ?r ?s)
        (not (OnTray ?r ?o ?s))
        (not (HandEmpty ?r))
        (increase (total-cost) (Cost))
    )
  )

  ;; ============================================================
  ;; Derived predicates
  ;; ============================================================

  (:derived (Holding ?r ?o)
    (or
      (exists (?g) (and (Grasp ?o ?g) (AtGrasp ?r ?o ?g)))
      (exists (?s) (and (TraySlot ?s) (OnTray ?r ?o ?s)))
    )
  )

  (:derived (In ?o ?reg)
    (exists (?p) (and (Pose ?o ?p) (Placeable ?o ?p ?reg) (AtPose ?o ?p)))
  )
)
