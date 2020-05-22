import json

# with open("raw/EGOT_winner.json") as f:
# 	data = json.load(f)
# 	for r in data:
# 		del r['Age at completion']
# 		del r['Started']
# 		del r['Year span']
# 		del r['Completed']
# 	#print(json.dumps(data))


# with open("raw/disasters.json", "r") as f:
# 	data = json.load(f)
# 	for r in data:
# 		for key, val in r.items():
# 			if val == None:
# 				r[key] = 0
# 		for key in ["Extreme weather", "Landslide", "Mass movement (dry)", "Volcanic activity", "Wildfire", "All natural disasters"]:
# 			del r[key]
# 	data = json.dumps([r for r in data if r["Year"] > 1960])
# 	print(data)

# with open("raw/pge-electric-data.json", "r") as f:
# 	data = json.load(f)
	
# 	data = json.dumps([r for r in data if r["DATE"].split("-")[1] in ["01", "02"] and int(r["START TIME"].split(":")[0]) % 2 == 0])
# 	#print(data)



# with open("raw/sea-ice-extent.json", "r") as f:
# 	data = json.load(f)
	
# 	data = json.dumps([r for r in data if int(r["date"].split("-")[0]) % 3 == 0 and int(r["date"].split("-")[2]) == 1])
# 	#print(data)

# with open("raw/weather.json", "r") as f:
# 	data = json.load(f)
	
# 	data = json.dumps([r for r in data if int(r["date"].split("-")[2]) % 5 == 0 or int(r["date"].split("-")[2]) == 1])
# 	#print(data)


# with open("raw/unemployment-rate.json", "r") as f:
# 	data = json.load(f)
	
# 	#data = json.dumps([r for r in data if (int(r["id"] / 1000) % 6 == 0)])

# 	data = sum([r["rate"] for r in data if int(r["id"] / 1000) == 6]) / len([r["rate"] for r in data if int(r["id"] / 1000) == 6])
# 	print(data)

# from collections import OrderedDict

with open("raw/car-sales.json", "r") as f:
	data = json.load(f)
	for r in data:
		del r["index"]
		del r["efficiency"]
		for key in ['Passenger Car (Domestic)', 'Passenger Car (Imported)', 'Light truck']:
			del r[key]

	#data = json.dumps(data)

	#sort_order = ['year', 'Passenger Car (Domestic)', 'Passenger Car (Imported)', 'Light truck', "sales"]
	#data = [OrderedDict(sorted(item.items(), key=lambda k: sort_order.index(k[0]))) for item in data]

	

	last_sale = None
	for r in data:
		temp = r["sales"]
		if last_sale != None:
			r["sales"] = r["sales"] - last_sale
		last_sale = temp

	data = json.dumps(data, indent=4, separators=(',', ': '))

	print(data)	
