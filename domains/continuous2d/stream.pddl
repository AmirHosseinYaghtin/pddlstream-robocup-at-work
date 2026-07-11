(define (stream robocup-continuous-tamp)

  ;; ============================================================
  ;; s-grasp : sample-grasp(object_type)
  ;; ============================================================
  (:stream s-grasp
    :inputs (?o)
    :domain (Object ?o)
    :outputs (?g)
    :certified (Grasp ?o ?g)
  )

  ;; ============================================================
  ;; s-region : sample a continuous placement pose for object ?o
  ;; inside region ?reg (table / shelf / box / workspace area).
  ;; This is the generic "give me somewhere to put it" sampler --
  ;; used both for plain pick-and-place (region = the target
  ;; table) and for sorting tasks (region = the correct bin).
  ;; ============================================================
  (:stream s-region
    :inputs (?o ?reg)
    :domain (and (Object ?o) (Region ?reg))
    :outputs (?p)
    :certified (and (Pose ?o ?p) (Placeable ?o ?p ?reg))
  )

  ;; ------------------------------------------------------------
  ;; t-region : test whether an already-produced pose ?p (e.g.
  ;; the object's current/observed pose) lies inside region ?reg.
  ;; Needed because AtPose facts from the initial state come from
  ;; perception, not from s-region, so In/Placeable must also be
  ;; checkable after the fact.
  ;; ------------------------------------------------------------
  (:stream t-region
    :inputs (?o ?p ?reg)
    :domain (and (Pose ?o ?p) (Region ?reg))
    :certified (Placeable ?o ?p ?reg)
  )

  ;; ============================================================
  ;; s-dock : sample-base-dock(object_pose)
  ;; ============================================================
  (:stream s-dock
    :inputs (?o ?p)
    :domain (Pose ?o ?p)
    :outputs (?bq)
    :certified (and (Dock ?o ?p ?bq) (BaseConf ?bq))
  )

  ;; ============================================================
  ;; s-ik : solve-ik(base_pose, object_pose, grasp)
  ;; Deliberately gated on (Dock ?o ?p ?bq) rather than a bare
  ;; (BaseConf ?bq), so IK is only ever attempted from base poses
  ;; that s-dock actually proposed for this (o, p) pair -- avoids
  ;; wasting IK calls on arbitrary/unrelated base configurations.
  ;; ============================================================
  (:stream s-ik
    :inputs (?o ?p ?g ?bq)
    :domain (and (Dock ?o ?p ?bq) (Grasp ?o ?g))
    :outputs (?aq)
    :certified (and (IK ?o ?p ?g ?bq ?aq) (ArmConf ?aq))
  )

  ;; ============================================================
  ;; s-base-motion : plan-base-motion(q_start, q_goal)
  ;; ============================================================
  (:stream s-base-motion
    :inputs (?bq1 ?bq2)
    :domain (and (BaseConf ?bq1) (BaseConf ?bq2))
    :outputs (?bt)
    :certified (and (BaseMotion ?bq1 ?bt ?bq2) (BaseTraj ?bt))
  )

  ;; ============================================================
  ;; s-arm-motion-free : plan-arm-motion(q_start, q_goal, holding=None)
  ;; used by pick (arm is empty on the way to the grasp config)
  ;; ============================================================
  (:stream s-arm-motion-free
    :inputs (?bq ?aq1 ?aq2)
    :domain (and (BaseConf ?bq) (ArmConf ?aq1) (ArmConf ?aq2))
    :outputs (?at)
    :certified (and (ArmMotionFree ?bq ?aq1 ?at ?aq2) (ArmTraj ?at))
  )

  ;; ============================================================
  ;; s-arm-motion-holding : plan-arm-motion(q_start, q_goal, holding=obj)
  ;; used by place (arm sweeps while carrying object ?o with
  ;; grasp ?g, so swept collision geometry differs from the free
  ;; case above)
  ;; ============================================================
  (:stream s-arm-motion-holding
    :inputs (?bq ?aq1 ?aq2 ?o ?g)
    :domain (and (BaseConf ?bq) (ArmConf ?aq1) (ArmConf ?aq2) (Grasp ?o ?g))
    :outputs (?at)
    :certified (and (ArmMotionHolding ?bq ?aq1 ?at ?aq2 ?o ?g) (ArmTraj ?at))
  )

  ;; ============================================================
  ;; t-base-cfree : collision-free(robot base traj vs. parked object)
  ;; Test stream (no :outputs) -- called on demand inside the
  ;; forall/imply block of move_base's precondition.
  ;; ============================================================
  (:stream t-base-cfree
    :inputs (?bt ?o2 ?p2)
    :domain (and (BaseTraj ?bt) (Pose ?o2 ?p2))
    :certified (BaseCFree ?bt ?o2 ?p2)
  )

  ;; ============================================================
  ;; t-arm-cfree : collision-free(arm traj vs. parked object)
  ;; Test stream, called inside pick's and place's forall/imply.
  ;; ============================================================
  (:stream t-arm-cfree
    :inputs (?bq ?at ?o2 ?p2)
    :domain (and (BaseConf ?bq) (ArmTraj ?at) (Pose ?o2 ?p2))
    :certified (ArmCFree ?bq ?at ?o2 ?p2)
  )

  ;; ============================================================
  ;; Cost functions
  ;; ============================================================
  (:function (Dist ?bq1 ?bq2)
    (and (BaseConf ?bq1) (BaseConf ?bq2))
  )

  (:function (ArmDist ?aq1 ?aq2)
    (and (ArmConf ?aq1) (ArmConf ?aq2))
  )

  (:function (ExtraBaseCost ?bq1 ?bq2)
    (and (BaseConf ?bq1) (BaseConf ?bq2))
  )

  ;; Note: (Cost) is NOT declared here. It's used in domain.pddl as
  ;; a flat per-action constant (pick/place/stow/unstow), not as
  ;; something a stream computes from inputs. Set it once in
  ;; problem.pddl's :init, e.g. (= (Cost) 1) -- no stream needed.
)
