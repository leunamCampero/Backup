SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Footway_path_designated_1x
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
						(
	"oneway" IN ('yes','-1')
	OR
	"oneway:bicycle" IN ('yes','-1')
)
AND
(
	(	--cas des footway
		"highway" LIKE 'footway' AND ( "footway" IS NULL OR "footway" NOT IN ('sidewalk'))
		AND
		"bicycle" IN ('designated','official')
	)
	OR
	(	--cas des path, on ne compte pas les voies vertes
		"highway" LIKE 'path'
		AND
		"bicycle" IN ('designated','official')
		AND
		(
			"foot" IS NULL
			OR
			"foot" NOT IN ('designated')
		)
	)
)
AND
(   -- Elles ont un revetement circulable au VTC vélo de randonnée ou le revetement n'est pas connu
    (
        (
            "surface" IN ('paved','asphalt','concrete','concrete:plates','concrete:lanes','paving_stones','sett','unhewn_cobblestone','cobblestone','metal','wood','unpaved','compacted','fine_gravel','gravel','pebblestone','ground','tartan','clay','metal_grid' )
            OR
            "surface" IS NULL
        )
        AND
        (
            "smoothness" NOT IN ('bad','very_bad','horrible','very_horrible','impassable')
            OR
            "smoothness" IS NULL
        )
        AND
        (
            "tracktype" NOT iN ('grade3','grade4','grade5')
            OR
            "tracktype" IS NULL
        )
    )
)

                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;