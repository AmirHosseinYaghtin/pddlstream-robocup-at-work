(define (stream robocup-discrete-tamp)

  ;; ------------------------------------------------------------
  ;; Rule: if a Kin relation is produced, then its arguments
  ;; are valid Conf and Pose objects.
  ;; ------------------------------------------------------------
  (:rule
    :inputs (?q ?p)
    :domain (Kin ?q ?p)
    :certified (and
      (Conf ?q)
      (Pose ?p))
  )

  ;; ------------------------------------------------------------
  ;; Stream: generate symbolic poses.
  ;; In Phase 1 these are predefined discrete poses such as:
  ;; table1_slot1, table1_slot2, shelf1_slot1, ...
  ;; In Phase 2 this can become continuous placement sampling.
  ;; ------------------------------------------------------------
  (:stream sample-pose
    :outputs (?p)
    :certified (Pose ?p)
  )

  ;; ------------------------------------------------------------
  ;; Stream: generate a robot configuration able to manipulate
  ;; an object at pose ?p.
  ;; In Phase 1 this is a lookup/enumeration.
  ;; In Phase 2 this can become IK / reachability reasoning.
  ;; ------------------------------------------------------------
  (:stream inverse-kinematics
    :inputs (?p)
    :domain (Pose ?p)
    :outputs (?q)
    :certified (Kin ?q ?p)
  )

)
