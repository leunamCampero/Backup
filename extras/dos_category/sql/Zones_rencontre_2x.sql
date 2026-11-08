SELECT
	jsonb_build_object(
		'type',
		'FeatureCollection',
		'features',
		jsonb_agg(feature)
	) as Zones_rencontre_2x
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
						--A double sens 
(
"oneway" IS NULL
OR
"oneway" LIKE 'no'
)

AND
	--soit une voie de type living street
	(
	"highway" LIKE 'living_street'

	OR
	
	--soit une voie avec le tag zone:maxspeed ou source:maxspeed
		( 
		"maxspeed"='20'
		AND
			(
			"zone:maxspeed"='FR:20'
			OR
			"source:maxspeed"='FR:zone20'
			)
		)
	)
	


                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;