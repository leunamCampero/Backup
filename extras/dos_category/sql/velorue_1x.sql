SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as velorue_1x
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
    "cyclestreet" = 'yes'
    OR
    "bicycle_road" = 'yes'
)

AND "oneway" IN ('yes','-1')

AND
(
	"bicycle" IS NULL
	OR
	"bicycle" NOT IN ('no')
)
                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;