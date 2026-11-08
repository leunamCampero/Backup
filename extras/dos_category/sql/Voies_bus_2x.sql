SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Voies_bus_2x
FROM
	(
		SELECT
			jsonb_build_object(
				'type',
				'Feature',
				'id',
				osm_id,
				'geometry',
				st_asgeojson(st_transform(way, 4326)) :: jsonb,
				'properties',
				to_jsonb(row) - 'gid' - 'geom'
			) AS feature
		FROM
			(
				SELECT
					*
				FROM
					planet_osm_line
				WHERE
					(
                        -- BEGIN GEOVELO SQL CONDITIONS
						-- On part du postula qu'une voie de bus en opposite_lane n'est pas un contre sens cyclable
-- Seules les voies de bus accessibles aux vélos sont comptabilisées

(
    ("oneway" IN ('yes','-1')) -- Soit une rue a sens unique
    AND
    (	--  les deux voies vélo sont spécifiées
        (
            (
                "cycleway:right" IN ('share_busway','opposite_share_busway')
                AND
                "cycleway:left" IN ('share_busway','opposite_share_busway')
            )
            OR
            "cycleway" IN ('share_busway','opposite_share_busway')
        )
        AND
        (
            "busway:right" IS NOT NULL
            AND
            "busway:right" NOT IN ('no')
        )
        AND
        (
            "busway:left" IS NOT NULL
            AND
            "busway:left" NOT IN ('no')
        )
    )
)
OR
(
    (	-- Dans tous les cas la route n'est pas à sens unique
        "oneway" IS NULL
        OR
        "oneway" NOT IN ('yes','-1')
    )
    AND
    (	-- et...
            -- Soit les voies de bus rattachées à une route (A)
        (	-- A1 - Soit les vélos ont accès à la voie bus
            "cycleway" IN ('share_busway')
            AND
            (	-- et il y a un voie bus des deux cotés
                "busway" NOT IN ('no')
                OR
                (
                    "busway:right" NOT IN ('no')
                    AND
                    "busway:left" NOT IN ('no')
                )
            )
        )
        OR
        (	-- A2 - Soit les deux voies vélo sont spécifiées
            "cycleway:right" IN ('share_busway')
            AND
            "cycleway:left" IN ('share_busway')
            AND
            (
                "busway:right" IS NOT NULL
                AND
                "busway:right" NOT IN ('no')
            )
            AND
            (
                "busway:left" IS NOT NULL
                AND
                "busway:left" NOT IN ('no')
            )
        )
        OR
        (	-- Soit les bus empruntent des voies indépendantes accessibles seulement aux vélos (B)
            "highway" IN ('service')
            AND
                ( -- a double sens
                    "oneway" IS NULL
                    OR
                    "oneway" NOT IN ('yes','-1')
                )
            AND
            (
                ("psv" IS NOT NULL OR "psv" NOT IN ('no'))
                OR
                ("bus" IS NOT NULL OR "psv" NOT IN ('no'))
            )
            AND
            ("access" IN ('no') OR "motor_vehicle" IN ('no'))
            AND
            (
                (
                "bicycle" IS NOT NULL
                AND
                "bicycle" NOT IN ('no')
                )
                OR
                (
                "cycleway" IN ('share_busway')
                OR
                (
                    "cycleway:right" IN ('share_busway')
                    AND
                    "cycleway:left" IN ('share_busway')
                )
                )
            )
        )
        OR
        (
            "highway" IN ('bus_guideway')
            AND
            (
                (
                "bicycle" IS NOT NULL
                AND
                "bicycle" NOT IN ('no')
                )
                OR
                (
                    "cycleway" IN ('share_busway')
                    OR
                    (
                        "cycleway:right" IN ('share_busway')
                        AND
                        "cycleway:left" IN ('share_busway')
                    )
                )
            )
        )
    )
)

                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;