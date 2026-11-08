SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Zones_30_1x
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
						-- Sont comptabilisés uniquement les zones 30 et pas les voies limitees à 30
-- Seul le sens voiture est pris en compte

"maxspeed" LIKE '30'
AND
(
	"zone:maxspeed" LIKE 'FR:30'
	OR
	"source:maxspeed" LIKE 'FR:zone30'
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