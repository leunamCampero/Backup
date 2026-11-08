SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Pistes_sur_Trottoirs_1x
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
						"segregated" LIKE 'yes'
AND
"highway" LIKE 'footway'
AND
"footway" LIKE 'sidewalk'
AND
"bicycle" NOT LIKE 'no'
AND
(
	"oneway" IN ('yes','-1')
	OR
	"oneway:bicycle" IN ('yes','-1')
)

                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;