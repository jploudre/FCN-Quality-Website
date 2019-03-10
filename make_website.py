#!/Users/jonathan/miniconda3/bin/python3

import glob as glob
import os
import shutil
import datetime as datetime
from multiprocessing import Pool
import jinja2
import json
import pandas as pd
import altair as alt
from weasyprint import HTML
import tqdm as tqdm
from selenium import webdriver

create_graphs = True
create_svgs = True
create_htmls = True
create_pdfs = True

names = pd.read_csv("./files/names.csv", index_col="MeridiosName")
metrics = pd.read_csv(
    "./files/metrics.csv", index_col="MeridiosMetric", dtype={"MeridiosMetric": object}
)

graphing_start_date = "1/1/2018"
graphing_end_date = "12/31/2019"
dark_purple = "#9467bd"
light_purple = "#c5b0d5"
dark_orange = "#ff7f0e"
light_orange = "#ffbb78"
dark_blue = "#1f77b4"
light_blue = "#aec7e8"
dark_green = "#2ca02c"
light_green = "#98df8a"

df = pd.DataFrame()

files = glob.iglob("./data/*.csv")
for file in tqdm.tqdm(files, total=len(glob.glob("./data/*csv")), desc="CSV Files"):
    file_df = pd.read_csv(file, usecols=["NAME", "Metricname", "SeenNum", "SeenDenom"])
    file_df["Name"] = file_df.NAME.map(names.Name)
    file_df["Type"] = file_df.NAME.map(names.Type)
    file_df["Clinic"] = file_df.NAME.map(names.Clinic)
    file_df["Metric"] = file_df.Metricname.map(metrics.Metric)

    # Meridios report doesn't have FCN summary so create it from clinic data.
    clinics_df = file_df[(file_df["Type"] == "Clinic")]
    fcn_data = []
    for metric in clinics_df.Metric.unique():
        metric_df = clinics_df[(clinics_df["Metric"] == metric)]
        fcn_numerator = metric_df.SeenNum.sum()
        fcn_denominator = metric_df.SeenDenom.sum()
        dataline = ("", "", fcn_numerator, fcn_denominator, "FCN", "FCN", "FCN", metric)
        fcn_data.append(dataline)
    fcn_df = pd.DataFrame.from_records(fcn_data, columns=metric_df.columns)
    file_df = file_df.append(fcn_df, ignore_index=True)

    # Manually Calculate percents, reduce precision.
    file_df["%"] = round(file_df["SeenNum"] / file_df["SeenDenom"], 4)
    file_df.drop(["SeenNum", "SeenDenom"], axis=1, inplace=True)

    # Meridios reports have unreliable datetimes. Uses Zero-Padded date on
    # filename for the date column.
    filename_parts = file[7:-4].split(" ")
    if len(str(filename_parts[0])) is 10:
        file_df["Date"] = datetime.datetime.strptime(filename_parts[0], "%m.%d.%Y")
        df = df.append(file_df)
    else:
        raise ValueError("Oops, CSV Filename require Zero Padded Dates")


if len(set(df.NAME.unique()) - set(names.index.unique())) > 1:
    print(
        "Missing Provider in names.csv:\n",
        set(df.NAME.unique()) - set(names.index.unique()),
    )

big_error_df = df[(df["%"] > 1)]
if not big_error_df.empty:
    print("Percentages can't be over 100:\n", big_error_df)

under_zero_df = df[(df["%"] < 0)]
if not under_zero_df.empty:
    print("Percentages can't be less than 0:\n", under_zero_df)
df.drop(["NAME"], axis=1, inplace=True)
df.drop(["Metricname"], axis=1, inplace=True)
df.dropna(subset=["Name"], inplace=True)
df.dropna(subset=["Metric"], inplace=True)


def make_individual_metric_json(metric, name_df, clinic_df, fcn_df, foldername):
    """
    Makes a chart json for a single metric and a single provider.
    Assumes: dataframes 'names' and 'metrics' for lookups
    """

    provider_df = name_df[(name_df["Metric"] == metric)]
    provider_df = provider_df.drop(["Metric"], axis=1)
    clinic_df = clinic_df[(clinic_df["Metric"] == metric)]
    clinic_df = clinic_df.drop(["Metric"], axis=1)
    fcn_df = fcn_df[(fcn_df["Metric"] == metric)]
    fcn_df = fcn_df.drop(["Metric"], axis=1)

    provider_current_metric = provider_df[provider_df["Date"] == current_date]

    metric_target = metrics[metrics.Metric == metric].iloc[0].Target

    if metric_target:
        metricdf = pd.DataFrame([{"TargetValue": metric_target, "Title": "Target"}])

    provider_progress_line = (
        alt.Chart(provider_df)
        .mark_line(strokeWidth=4)
        .encode(
            alt.X(
                "Date:T",
                title="",
                scale=alt.Scale(domain=(graphing_start_date, graphing_end_date)),
            ),
            alt.Y(
                "%:Q",
                axis=alt.Axis(format="%", title=""),
                scale=alt.Scale(domain=(0, 1)),
            ),
            color=alt.ColorValue(dark_purple),
        )
        .properties(width=350, height=200)
    )

    provider_current_text = (
        alt.Chart(provider_current_metric)
        .mark_text(align="right", baseline="top", dx=175, dy=-98, size=16)
        .encode(text=alt.Text("%:Q", format=".2%"), color=alt.ColorValue(dark_purple))
    )

    clinic_progress_line = (
        alt.Chart(clinic_df)
        .mark_line(strokeWidth=2)
        .encode(
            alt.X("Date:T", title=""), alt.Y("%:Q"), color=alt.ColorValue(light_orange)
        )
    )

    fcn_progress_line = (
        alt.Chart(fcn_df)
        .mark_line(strokeWidth=2)
        .encode(
            alt.X("Date:T", title=""), alt.Y("%:Q"), color=alt.ColorValue(light_blue)
        )
    )

    if metric_target:
        metric_target_rule = (
            alt.Chart(metricdf)
            .mark_rule(strokeWidth=1, strokeDash=[4, 2])
            .encode(y="TargetValue:Q", color=alt.ColorValue(dark_green))
        )
        metric_target_text = (
            alt.Chart(metricdf)
            .mark_text(align="right", baseline="bottom", dx=175, dy=100, size=16)
            .encode(
                text=alt.Text("TargetValue:Q", format=".2%"),
                color=alt.ColorValue(dark_green),
            )
        )

        if metric_target:
            chart = (
                fcn_progress_line
                + clinic_progress_line
                + provider_progress_line
                + metric_target_rule
                + metric_target_text
                + provider_current_text
            )
        else:
            chart = fcn_progress_line + clinic_progress_line + provider_progress_line

    if create_svgs:
        chart.save(foldername + metric + ".svg")

    return chart.to_json()


def save_individual_chart_data(name):
    json_data = ""

    clinic_name = names[names.Name == name].iloc[0].Clinic
    name_df = df[(df["Name"] == name)]
    name_df = name_df.drop(["Name", "Type", "Clinic"], axis=1)
    clinic_df = df[(df["Name"] == clinic_name)]
    clinic_df = clinic_df.drop(["Name", "Type", "Clinic"], axis=1)
    foldername = savefolder(name)

    for metric in main_metrics:
        chart_data = make_individual_metric_json(
            metric, name_df, clinic_df, fcn_df, foldername
        )
        chart_data_json = json.loads(chart_data)
        json_minified = json.dumps(chart_data_json, separators=(",", ":"))
        json_data += "var " + metric.replace(" ", "_") + " = " + json_minified + ";\n"
    with open(foldername + "chart_data.json", "w") as savefile:
        savefile.write(json_data)


def make_clinic_metric_json(metric, clinic_name, clinic_df, fcn_df):
    """
    Makes a chart for a single metric and a clinic.

    Assumes: dataframe 'df' that has all the data from CSVs
    Assumes: dataframes 'names' and 'metrics' for lookups
    """

    clinic_df = clinic_df[(clinic_df["Metric"] == metric)]
    clinic_df = clinic_df.drop(["Metric"], axis=1)

    fcn_df = fcn_df[(fcn_df["Metric"] == metric)]
    fcn_df = fcn_df.drop(["Metric"], axis=1)

    metric_target = metrics[metrics.Metric == metric].iloc[0].Target
    if metric_target:
        metricdf = pd.DataFrame([{"TargetValue": metric_target, "Title": "Target"}])

    current_metric = df[
        (df["Metric"] == metric)
        & (df["Type"] == "Clinic")
        & (df["Date"] == current_date)
    ]

    clinic_current_metric = df[
        (df["Metric"] == metric)
        & (df["Name"] == clinic_name)
        & (df["Date"] == current_date)
    ]

    clinic_progress_line = (
        alt.Chart(clinic_df)
        .mark_line(strokeWidth=4)
        .encode(
            alt.X(
                "Date:T",
                title="",
                scale=alt.Scale(domain=(graphing_start_date, graphing_end_date)),
            ),
            alt.Y(
                "%:Q",
                axis=alt.Axis(format="%", title=""),
                scale=alt.Scale(domain=(0, 1)),
            ),
            color=alt.ColorValue(dark_orange),
        )
        .properties(width=200, height=200)
    )

    clinic_progress_text = (
        alt.Chart(clinic_current_metric)
        .mark_text(align="right", baseline="top", dx=100, dy=-98, size=16)
        .encode(text=alt.Text("%:Q", format=".2%"), color=alt.ColorValue(dark_orange))
    )

    fcn_progress_line = (
        alt.Chart(fcn_df)
        .mark_line(strokeWidth=2)
        .encode(
            alt.X("Date:T", title=""),
            alt.Y(
                "%:Q",
                axis=alt.Axis(format="%", title=""),
                scale=alt.Scale(domain=(0, 1)),
            ),
            color=alt.ColorValue(light_blue),
        )
    )

    if metric_target:
        metric_target_rule = (
            alt.Chart(metricdf)
            .mark_rule(strokeWidth=1, strokeDash=[4, 2])
            .encode(y="TargetValue:Q", color=alt.ColorValue(dark_green))
        )
        metric_target_text = (
            alt.Chart(metricdf)
            .mark_text(align="right", baseline="bottom", dx=100, dy=100, size=16)
            .encode(
                text=alt.Text("TargetValue:Q", format=".2%"),
                color=alt.ColorValue(dark_green),
            )
        )
    clinic_providers = sorted(
        single_providers[single_providers.Clinic == clinic_name].Name.unique(),
        key=lambda x: x.split(" ")[1],
    )

    current_metric = df[
        (df["Metric"] == metric)
        & (df["Date"] == current_date)
        & (df["Name"].isin(clinic_providers))
    ]
    current_metric = current_metric.drop(["Type", "Clinic", "Metric", "Date"], axis=1)

    start_date = min(clinic_df["Date"])
    start_metric = df[
        (df["Metric"] == metric)
        & (df["Date"] == start_date)
        & (df["Name"].isin(clinic_providers))
    ]
    start_metric = start_metric.drop(["Type", "Clinic", "Metric", "Date"], axis=1)
    start_and_current = pd.concat([start_metric, current_metric])

    ranged_dot = (
        alt.Chart(start_and_current)
        .mark_line(color=light_purple)
        .encode(
            alt.Y(
                "%:Q",
                axis=alt.Axis(format="%", title=""),
                scale=alt.Scale(domain=(0, 1)),
            ),
            alt.X("Name:N", axis=alt.Axis(title=""), sort=clinic_providers),
            detail="Name:N",
        )
        .properties(height=200)
    )

    ranged_dot += (
        alt.Chart(current_metric)
        .mark_point(size=100, opacity=1, filled=True, color=dark_purple)
        .encode(alt.Y("%:Q"), alt.X("Name:N", sort=clinic_providers))
    )

    ranged_dot_rule = (
        alt.Chart(metricdf)
        .mark_rule(strokeWidth=1, strokeDash=[4, 2])
        .encode(y="TargetValue:Q", color=alt.value(dark_green))
    )

    if metric_target:
        chart = (
            fcn_progress_line
            + clinic_progress_line
            + metric_target_rule
            + metric_target_text
            + clinic_progress_text
        ) | ranged_dot + ranged_dot_rule
    else:
        chart = (fcn_progress_line + clinic_progress_line) | ranged_dot
    return chart.to_json()


def save_clinic_chart_data(clinic_name):
    json_data = ""
    clinic_df = df[(df["Name"] == clinic_name)]
    clinic_df = clinic_df.drop(["Name", "Type", "Clinic"], axis=1)

    for metric in main_metrics:
        chart_data = make_clinic_metric_json(metric, clinic_name, clinic_df, fcn_df)
        chart_data_json = json.loads(chart_data)
        json_minified = json.dumps(chart_data_json, separators=(",", ":"))
        json_data += "var " + metric.replace(" ", "_") + " = " + json_minified + ";\n"
    foldername = savefolder(clinic_name)
    with open(foldername + "chart_data.json", "w") as savefile:
        savefile.write(json_data)


def make_fcn_metric_json(metric):
    """
    Makes a chart for a single metric for FCN.

    Assumes: dataframe 'df' that has all the data from CSVs
    Assumes: dataframes 'names' and 'metrics' for lookups
    """

    fcn_df = df[(df["Metric"] == metric) & (df["Type"] == "FCN")]
    fcn_df = fcn_df.drop(["Name", "Type", "Clinic", "Metric"], axis=1)

    fcn_current_metric = df[
        (df["Metric"] == metric) & (df["Name"] == "FCN") & (df["Date"] == current_date)
    ]

    metric_target = metrics[metrics.Metric == metric].iloc[0].Target
    if metric_target:
        metricdf = pd.DataFrame([{"TargetValue": metric_target, "Title": "Target"}])

    fcn_progress_line = (
        alt.Chart(fcn_df)
        .mark_line(strokeWidth=4)
        .encode(
            alt.X(
                "Date:T",
                title="",
                scale=alt.Scale(domain=(graphing_start_date, graphing_end_date)),
            ),
            alt.Y(
                "%:Q",
                axis=alt.Axis(format="%", title=""),
                scale=alt.Scale(domain=(0, 1)),
            ),
            color=alt.ColorValue(dark_blue),
        )
        .properties(width=200, height=200)
    )
    fcn_progress_line += (
        alt.Chart(fcn_current_metric)
        .mark_text(align="right", baseline="top", dx=100, dy=-98, size=16)
        .encode(text=alt.Text("%:Q", format=".2%"), color=alt.ColorValue(dark_blue))
    )

    if metric_target:
        metric_target_rule = (
            alt.Chart(metricdf)
            .mark_rule(strokeWidth=1, strokeDash=[4, 2])
            .encode(y="TargetValue:Q", color=alt.ColorValue(dark_green))
        )
        metric_target_rule += (
            alt.Chart(metricdf)
            .mark_text(align="right", baseline="bottom", dx=100, dy=100, size=16)
            .encode(
                text=alt.Text("TargetValue:Q", format=".2%"),
                color=alt.ColorValue(dark_green),
            )
        )

    current_metric = df[
        (df["Metric"] == metric)
        & (df["Date"] == current_date)
        & (df["Type"] == "Clinic")
    ]
    current_metric = current_metric.drop(["Type", "Clinic", "Metric", "Date"], axis=1)

    start_date = min(fcn_df["Date"])
    start_metric = df[
        (df["Metric"] == metric) & (df["Date"] == start_date) & (df["Type"] == "Clinic")
    ]
    start_metric = start_metric.drop(["Type", "Clinic", "Metric", "Date"], axis=1)

    start_and_current = pd.concat([start_metric, current_metric])

    ranged_dot = (
        alt.Chart(start_and_current)
        .mark_line(color=light_orange)
        .encode(
            alt.Y(
                "%:Q",
                axis=alt.Axis(format="%", title=""),
                scale=alt.Scale(domain=(0, 1)),
            ),
            alt.X("Name:N", axis=alt.Axis(title="")),
            detail="Name:N",
        )
        .properties(height=200)
    )

    ranged_dot += (
        alt.Chart(current_metric)
        .mark_point(size=100, opacity=1, filled=True, color=dark_orange)
        .encode(alt.Y("%:Q"), alt.X("Name:N"))
    )

    ranged_dot_rule = (
        alt.Chart(metricdf)
        .mark_rule(strokeWidth=1, strokeDash=[4, 2])
        .encode(y="TargetValue:Q", color=alt.value(dark_green))
    )

    if metric_target:
        chart = (metric_target_rule + fcn_progress_line) | ranged_dot + ranged_dot_rule
    else:
        chart = (fcn_progress_line) | ranged_dot
    return chart.to_json()


# In names dataframe, if data in individual column then it's an active person
single_providers = names[(names["Type"] == "Individual")]

sorted_single_provider_names = sorted(
    single_providers.Name.unique(), key=lambda x: x.split(" ")[1]
)
clinics = sorted(set(df[(df["Type"] == "Clinic")].Name.unique()))
main_metrics = sorted(set(metrics[(metrics["Main"] == "Main")].Metric.unique()))
current_date = max(df["Date"])
current_date_string = current_date.strftime("%m/%d/%Y")


def savefolder(name):
    foldername = str(name).replace(" ", "_")
    if not os.path.exists("./docs/" + foldername):
        os.makedirs("./docs/" + foldername)
    return "./docs/" + foldername + "/"


def create_full_html(provider):
    with open(
        "./docs/" + provider.replace(" ", "_") + "/chart_data.json", "r"
    ) as chart_data:
        chart_data_text = chart_data.read()
        new_custom_javascript = custom_javascript.replace(
            "<!--JSON-->", chart_data_text
        )
    templateLoader = jinja2.FileSystemLoader(searchpath="./files/")
    templateEnv = jinja2.Environment(
        loader=templateLoader,
        trim_blocks=True,
        lstrip_blocks=True,
        line_statement_prefix="#",
    )
    TEMPLATE_FILE = "index.html"
    template = templateEnv.get_template(TEMPLATE_FILE)
    template_weasy = templateEnv.get_template("index-weasy.html")
    providertype = names[names.Name == provider].iloc[0].Type
    clinic_name = names[names.Name == provider].iloc[0].Clinic
    same_clinic_providers = sorted(
        single_providers[single_providers.Clinic == clinic_name].Name.unique(),
        key=lambda x: x.split(" ")[1],
    )
    filedata = template.render(
        current_date_string=current_date_string,
        new_custom_javascript=new_custom_javascript,
        providertype=providertype,
        provider=provider,
        clinic_name=clinic_name,
        same_clinic_providers=same_clinic_providers,
        clinics=clinics,
    )
    with open(savefolder(provider) + "index.html", "w+") as file:
        file.write(filedata)

    filedata_weasy = template_weasy.render(
        current_date_string=current_date_string,
        provider=provider,
        clinic_name=clinic_name,
    )
    with open(savefolder(provider) + "index-weasy.html", "w+") as file:
        file.write(filedata_weasy)


FCN_logo = "./files/pictures/logo.png"
if os.path.isfile(FCN_logo):
    if not os.path.exists("./docs/pictures/"):
        os.makedirs("./docs/pictures/")
    shutil.copyfile(FCN_logo, "./docs/pictures/logo.png")

if not os.path.exists("./docs/js/"):
    os.makedirs("./docs/js/")
files = glob.glob("./files/js/*.js")
for file in files:
    _, tail = os.path.split(file)
    shutil.copyfile(file, "./docs/js/" + str(tail))

css = "./files/uikit.min.css"
if os.path.isfile(css):
    shutil.copyfile(css, "./docs/uikit.min.css")

favicon = "./files/pictures/favicon.ico"
if os.path.isfile(favicon):
    shutil.copyfile(favicon, "./docs/favicon.ico")

comet_chart = "./files/pictures/quality_comet.png"
if os.path.isfile(comet_chart):
    shutil.copyfile(comet_chart, "./docs/quality_comet.png")


fcn_df = df[(df["Name"] == "FCN")]
fcn_df = fcn_df.drop(["Name", "Type", "Clinic"], axis=1)

if create_graphs:
    pool = Pool()
    for _ in tqdm.tqdm(
        pool.imap(save_individual_chart_data, sorted_single_provider_names),
        total=len(sorted_single_provider_names),
        desc="   Graphs",
    ):
        pass
    pool.close()
    pool.join()

if create_graphs:
    pool2 = Pool()
    for _ in tqdm.tqdm(
        pool2.imap(save_clinic_chart_data, clinics),
        total=len(clinics),
        desc="   Graphs",
    ):
        pass
    pool2.close()
    pool2.join()


if create_graphs:
    json_data = ""
    name = "FCN"
    for metric in main_metrics:
        chart_data = make_fcn_metric_json(metric)
        chart_data_json = json.loads(chart_data)
        json_minified = json.dumps(chart_data_json, separators=(",", ":"))
        json_data += "var " + metric.replace(" ", "_") + " = " + json_minified + ";\n"
    foldername = savefolder(name)
    with open(foldername + "chart_data.json", "w") as savefile:
        savefile.write(json_data)

with open("./files/js/jkp_custom.js", "r") as customjs:
    custom_javascript = customjs.read()

for provider in sorted_single_provider_names:
    provider_picture = "./files/pictures/" + str(provider).replace(" ", "_") + ".JPG"
    if os.path.isfile(provider_picture):
        shutil.copyfile(
            provider_picture,
            "./docs/pictures/" + str(provider).replace(" ", "_") + ".JPG",
        )
    else:
        print("Missing photo:", provider_picture)
if create_htmls:
    all_individual_clinic_fcn = names[
        (names["Type"].isin(["Individual", "Clinic", "FCN"]))
    ].Name.unique()
    for provider in all_individual_clinic_fcn:
        create_full_html(provider)

# Base HTML File
root_index_clinic = (
    '<div uk-filter="target: .js-filter"><ul class="uk-subnav uk-subnav-pill">\n'
)

for clinic in clinics:
    root_index_clinic += (
        '<li uk-filter-control=".tag-'
        + clinic
        + '"><a href="#">'
        + clinic
        + "</a></li>\n"
    )
root_index_clinic += "</ul>"

provider_index_cards = '<ul class="js-filter uk-grid-match uk-card-small" uk-grid>\n'

for name in sorted_single_provider_names:
    provider_icon = (
        '<img class="uk-border-circle" src="'
        + "./pictures/"
        + str(name).replace(" ", "_")
        + ".JPG"
        + '" width="64" height="64" class="">&nbsp;&nbsp;'
    )
    provider_index_cards += (
        '<li class="tag-'
        + names[names.Name == name].iloc[0].Clinic
        + '"><a class="" href="./'
        + str(name).replace(" ", "_")
        + '/"><div class="uk-card uk-width-medium uk-card-hover uk-card-default uk-card-body">'
        + provider_icon
        + name
        + "</div></a></li>\n"
    )
provider_index_cards += "</ul>"

with open("./files/index-base.html", "r") as file:
    filedata = file.read()
filedata = filedata.replace("<!--CLINICS-->", root_index_clinic)
filedata = filedata.replace("<!--Provider-Index-Cards-->", provider_index_cards)
filedata = filedata.replace("{{{Current Date}}}", current_date_string)
with open("docs/" + "index.html", "w+") as file:
    file.write(filedata)


def pdf_folder(name):
    foldername = str(name).replace(" ", "_")
    if not os.path.exists("./docs/" + foldername):
        os.makedirs("./docs/" + foldername)
    return "/docs/" + foldername + "/"


def make_pdf(provider):
    HTML(
        "http://0.0.0.0:8000{}index-weasy.html".format(pdf_folder(provider))
    ).write_pdf(target=".{}{}.pdf".format(pdf_folder(provider), provider))


if create_pdfs:
    pool = Pool()
    for _ in tqdm.tqdm(
        pool.imap(make_pdf, single_providers.Name.unique()),
        total=len(single_providers),
        desc="     PDFs",
    ):
        pass
    pool.close()
    pool.join()


# Remove all the temporary files now
for file in glob.iglob("./docs/**/*.json", recursive=True):
    os.remove(file)
for file in glob.iglob("./docs/**/index-weasy.html", recursive=True):
    os.remove(file)
