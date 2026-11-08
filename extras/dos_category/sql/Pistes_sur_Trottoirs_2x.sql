SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Pistes_sur_Trottoirs_2x
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
						( --modélisation avec un way séparé
    "segregated" LIKE 'yes'
    AND
    "highway" LIKE 'footway'
    AND
    "footway" LIKE 'sidewalk'
    AND
    "bicycle" IN ('yes', 'designated', 'official')
    AND
    (
        (
            "oneway" IS NULL
            OR
            "oneway" LIKE 'no'
        )
        AND
        (
            "oneway:bicycle" IS NULL
            OR
            "oneway:bicycle" LIKE 'no'
        )
    )
)
OR
(  --modélisation sur la voirie

    "sidewalk" = 'both'
    AND
    (
        "sidewalk:both:bicycle" IN ('yes', 'designated', 'official')
        OR
        (
           "sidewalk:right:bicycle" IN ('yes', 'designated', 'official')
           AND
           "sidewalk:left:bicycle" IN ('yes', 'designated', 'official')
        )
    )
    AND
    (
        "sidewalk:segregated" = 'yes'
        OR
        "sidewalk:both:segregated" = 'yes'
    )
)
                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;