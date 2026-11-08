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
 "bicycle" IS NOT NULL 
            OR "cycleway" IS NOT NULL
            OR "cycleway:left" IS NOT NULL
            OR "cycleway:right" IS NOT NULL
            OR "cycleway:both" IS NOT NULL
            OR "cycleway:left:oneway" IS NOT NULL
            OR "cycleway:right:oneway" IS NOT NULL
                        -- END GEOVELO SQL CONDITIONS
					)
			) row
	) features;