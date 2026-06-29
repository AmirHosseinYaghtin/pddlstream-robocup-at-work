(define (domain robocup-discrete-tamp)

  (:requirements :strips :equality)

  (:predicates

    ;; ---------------------------
    ;; Types encoded as predicates
    ;; ---------------------------

    (Conf ?q)           ;; robot configuration
    (Pose ?p)           ;; object placement pose
    (Object ?o)         ;; movable object

    ;; ---------------------------
    ;; Robot state
    ;; ---------------------------

    (AtConf ?q)         ;; robot is at configuration q
    (HandEmpty)         ;; gripper empty
    (Holding ?o)        ;; holding object o
    (CanMove)           ;; gating predicate to separate move/pick/place


    ;; ---------------------------
    ;; Object state
    ;; ---------------------------

    (AtPose ?o ?p)      ;; object o is at pose p


    ;; ---------------------------
    ;; Feasibility relations
    ;; ---------------------------
    (Clear ?p)          ;; to check if a pose is clear to place or not
    (Kin ?q ?p)         ;; configuration q can manipulate pose p

  )


  ;; ============================================================
  ;; Move Action
  ;; ============================================================

  (:action move
    :parameters (?q1 ?q2)
    :precondition (and
        (Conf ?q1)
        (Conf ?q2)
        (AtConf ?q1)
        (CanMove)
    )
    :effect (and
        (AtConf ?q2)
        (not (AtConf ?q1))
        (not (CanMove))
    )
  )


  ;; ============================================================
  ;; Pick Action
  ;; ============================================================

  (:action pick
    :parameters (?o ?p ?q)
    :precondition (and
        (Object ?o)
        (Pose ?p)
        (Conf ?q)

        (Kin ?q ?p)
        (AtConf ?q)
        (AtPose ?o ?p)
        (HandEmpty)
    )
    :effect (and
        (Holding ?o)
        (CanMove)
        (not (AtPose ?o ?p))
        (Clear ?p)
        (not (HandEmpty))
    )
  )


  ;; ============================================================
  ;; Place Action
  ;; ============================================================

  (:action place
    :parameters (?o ?p ?q)
    :precondition (and
        (Object ?o)
        (Pose ?p)
        (Conf ?q)

        (Kin ?q ?p)
        (AtConf ?q)
        (Holding ?o)
        (Clear ?p)
    )
    :effect (and
        (AtPose ?o ?p)
        (HandEmpty)
        (CanMove)
        (not (Holding ?o))
        (not (Clear ?p))
    )
  )
)
