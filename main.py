from datetime import datetime, timedelta, time
from io import BytesIO

import pytz as pytz
from flask import Flask, request
import os
from dotenv import load_dotenv
from conector import conectorbd
from flask import jsonify, send_file
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity
from flask_cors import CORS, cross_origin
from flask_swagger_ui import get_swaggerui_blueprint
from liquidacion import liquidacionmes
from funcionario import Funcionario
from werkzeug.utils import secure_filename
from liquidacionArchivo import liquidacion_mes, delete_files_in_directory
import csv
import zipfile
import re

app = Flask(__name__)
CORS(app, resources={r'/apiliquidacionmasiva/*': {'origins': '*'}})
hoy = datetime.now()
dateFormatter = "%Y-%m-%d"
load_dotenv()  # para leer las variables del archivo .env
URI_API = os.getenv('URI_API')
app.config["JWT_SECRET_KEY"] = os.getenv('JWT_SECRET')  # necesario para generar el token
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
jwt = JWTManager(app)

SWAGGER_URL = '/api/docs'
API_URL = '/static/swaggerApi.yaml'
swagger_ui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,  # Swagger UI static files will be mapped to '{SWAGGER_URL}/dist/'
    API_URL,
    config={  # Swagger UI config overrides
        'app_name': "application remuneraciones P.9"
    },
    # oauth_config={  # OAuth config. See https://github.com/swagger-api/swagger-ui#oauth2-configuration .
    #    'clientId': "your-client-id",
    #    'clientSecret': "your-client-secret-if-required",
    #    'realm': "your-realms",
    #    'appName': "your-app-name",
    #    'scopeSeparator': " ",
    #    'additionalQueryStringParams': {'test': "hello"}
    # }
)
app.register_blueprint(swagger_ui_blueprint, url_prefix=SWAGGER_URL)
zona_cl = pytz.timezone('America/Santiago')
# hoy = datetime.now()

UPLOAD_FOLDER = 'csv'
ALLOWED_EXTENSIONS = {'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/' + URI_API + '/bienvenidos')
def bienvenidos():
    return jsonify({'status': 200, 'message': 'Bienvenidos a la API REST del Departamento P9'}), 200


@app.route('/' + URI_API + '/login', methods=["POST"])
@cross_origin()
def login():
    try:
        if not request.args.get('rut'):
            return jsonify({'msg': 'Gracias por intentarlo ojon!!'}), 401
        rut = str(request.args.get('rut')).strip()
        rut = rut[:-1]
        datos = []
        datos2 = []
        datos3 = []
        datos4 = []
    except Exception as error:
        return jsonify({'msg': 'Problemas en login ' + str(error).strip()}), 401

    try:
        conn = conectorbd()
        cursor = conn.cursor()
        cursor.execute("EXEC BD_PERFIL.dbo.sp_consultar_autorizado " + rut)
        filas = cursor.fetchall()
        cursor.close()
        if filas:
            for row in filas:
                datos.append(
                    {'id_rut': row[0],
                     'dt_digito': row[1],
                     'dt_clave': row[2],
                     'dt_nombre': row[3],
                     'dt_repartition': row[4],
                     'dt_correo': row[5].strip(),
                     'dt_control_liq': row[6].strip(),
                     'dt_cargo': row[7].strip(),
                     'dt_activo': row[8],
                     'dt_glosa': row[9].strip(),
                     'dt_fecha_expira': row[10],
                     'dt_restriction': row[11].strip(),
                     'dt_fecha_hoy': row[12].strip(),
                     'dt_activo_2': row[13].strip()
                     })
            fecha_exp = datos[0]['dt_fecha_expira']
            dia_expira = fecha_exp[6:]
            mes_expira = fecha_exp[4:-2]
            anno_expira = fecha_exp[:-4]
            date_expira = datetime.strptime(anno_expira + "-" + mes_expira + "-" + dia_expira, dateFormatter)
            if hoy > date_expira:
                return jsonify({'msg': 'Su perfil a caducado'}), 401

            if datos[0]['dt_activo'] == "N":
                return jsonify({'msg': 'Estimado usuario, su perfil no esta activo'}), 401

    except Exception as error:
        return jsonify({'msg': 'No tiene permisos asociados ' + str(error).strip()}), 401

    try:
        conn = conectorbd()
        cursor = conn.cursor()
        cursor.execute("EXEC BD_REMUNE.dbo.sp_consultar_funcionario " + rut)
        filas2 = cursor.fetchall()
        cursor.close()
        if filas2:
            for row2 in filas2:
                datos2.append({
                    'id_rut': row2[0],
                    'dt_digito': row2[1],
                    'dt_cod': row2[2],
                    'dt_letra': row2[3],
                    'paterno': row2[4],
                    'materno': row2[5],
                    'nombre': row2[6],
                    'fecha_nacimiento': row2[7],
                    'fecha_ingreso': row2[8],
                    'fecha_retiro': row2[9],
                    'sexo': row2[10],
                    'estado_civil': row2[11],
                    'nombre2': row2[12],
                    'cod_funcionario1': row2[2] + "-" + row2[3]
                })
        else:
            return jsonify({'msg': 'No es posible cargar la información del funcionario'}), 403
    except Exception as error:
        return jsonify({'msg': 'Problemas al cargar la información del funcionario.' + str(error).strip()})

    try:
        conn = conectorbd()
        cursor = conn.cursor()
        cursor.execute("EXEC BD_PERFIL.dbo.sp_consultar_perfil_usuario " + rut + ", '', 'PAGM', ''")  # PAGM para liquidacion masiva
        fila3 = cursor.fetchall()
        cursor.close()
        if fila3:
            for row4 in fila3:
                datos3.append({
                    "rut": row4[0],
                    "id_ucf": row4[1],
                    "id_sistema": row4[2],
                    "dt_function": row4[3],
                    "dt_repartition_desde": row4[4],
                    "dt_repartition_hasta": row4[5],
                    "dt_repartition_centra": row4[6],
                    "dt_filtro": row4[7],
                    "dt_multi_dotacion": row4[8],
                    "dt_grado": row4[9],
                    "dt_acceso_alto_mando": row4[10],
                    "dt_super_usuario": row4[11],
                    "id_option": row4[12]
                })
        else:
            return jsonify({'msg': 'No tiene permisos para este sistema'}), 401
    except Exception as error:
        return jsonify({'msg': 'Problemas al intentar obtener información de perfil', 'error': str(error)}), 401

    try:
        conn = conectorbd()
        cursor = conn.cursor()
        cursor.execute("EXEC BD_PERFIL.dbo.sp_consultar_perfil_usuario " + rut + ", '', 'PAG', ''")
        rows4 = cursor.fetchall()
        cursor.close()
        for row4 in rows4:
            ## print('login row4 -> ', row4)
            login_ucf = row4[1]
            datos4.append({
                "rut": row4[0],
                "id_ucf": row4[1],
                "id_sistema": row4[2],
                "dt_funcion": row4[3],
                "dt_reparticion_desde": row4[4],
                "dt_reparticion_hasta": row4[5],
                "dt_reparticion_centra": row4[6],
                "dt_filtro": row4[7],
                "dt_multi_dotacion": row4[8],
                "dt_grado": row4[9],
                "dt_acceso_altomando": row4[10],
                "dt_super_usuario": row4[11],
                "id_opcion": row4[12]
            })
    except Exception as error:
        return jsonify({'error': error, 'msg': 'Problemas al obtener alto mando'}), 401

    try:
        access_token = create_access_token(identity={'datos': datos, 'datos2': datos2, 'datos3': datos3, 'datos4': datos4})
        return jsonify(token=access_token), 200
    except Exception as error:
        return jsonify({'msg': 'No es posible generar un token para el sistema', 'error': str(error)}), 401


@app.route('/' + URI_API + '/validar_token', methods=["GET"])
@jwt_required()
def validar_token():
    # Access the identity of the current user with get_jwt_identity
    current_user = get_jwt_identity()
    # return jsonify(logged_in_as=current_user), 200
    return jsonify(current_user)


@app.route('/' + URI_API + '/listar_funcionarios', methods=["POST"])
@jwt_required()
def listar_funcionario():
    try:
        if not request.args.get('paterno') and not request.args.get('materno'):
            return jsonify({'msg': 'No hay parámetros para la búsqueda'}), 401
        else:
            funcionarios = []
            paterno = str(request.args.get('paterno')).strip()
            materno = str(request.args.get('materno')).strip()
            if materno != '' or paterno != '':
                conn = conectorbd()
                cursor = conn.cursor()
                cursor.execute("EXEC BD_REMUNE.dbo.sp_listar_funcionarios '" + paterno + "', '" + materno + "'")
                list_funcionarios = cursor.fetchall()
                cursor.close()

                if list_funcionarios:
                    funcionarios = Funcionario.informacion(list_funcionarios)
                    # print(funcionarios)
                    return jsonify({'lists': funcionarios, 'status': 200, 'description': 'Listado de funcionarios encontrados según búsqueda.'}), 200
                else:
                    return jsonify({'msg': 'No se encontró a ningún funcionario asociada a la búsqueda ingresada.', 'status': 404}), 404
    except Exception as error:
        return jsonify({'msg': 'Problemas en login ', 'error': str(error)}), 401


@app.route('/' + URI_API + '/ultima-liquidacion-habilitada', methods=['GET'])
# @jwt_required()
def ultima_liquidacion():
    # if not request.args.get('sitio') or request.args.get('sitio') != 'LIQ':
    #    return jsonify({'msg': 'Gracias por intentarlo !!'}), 404
    array_ultima = []
    conn = conectorbd()
    cursor = conn.cursor()
    cursor.execute('EXEC BD_REMUNE.dbo.sp_consultar_ultima_liquidacion')
    ultima_fecha = cursor.fetchall()
    cursor.close()
    for data in ultima_fecha:
        array_ultima.append({'anno': data[0], 'mes': data[1], 'mes_string': mes_string(data[1])})
    return jsonify(array_ultima), 200


def mes_string(id_mes):
    match id_mes:
        case 1:
            return 'Enero'
        case 2:
            return 'Febrero'
        case 3:
            return 'Marzo'
        case 4:
            return 'Abril'
        case 5:
            return 'Mayo'
        case 6:
            return 'Junio'
        case 7:
            return 'Julio'
        case 8:
            return 'Agosto'
        case 9:
            return 'Septiembre'
        case 10:
            return 'Octubre'
        case 11:
            return 'Noviembre'
        case 12:
            return 'Diciembre'
        case _:
            return ''


@app.route('/' + URI_API + '/anos_institucionales', methods=['POST'])
@jwt_required()
def anos_institucionales():
    # print(request.args)
    if not request.args.get("rut"):
        return jsonify({"msg": "Gracias por intentarlo !!!"}), 401

    rut = request.args.get("rut", None).strip()
    conn = conectorbd()
    cursor = conn.cursor()
    # cursor.execute("SELECT SUBSTRING(CAST(ID_FECHA AS VARCHAR(6)),1,4) FROM BD_REMUNE.DBO.TA_BILLETAJE_PAGOS WHERE ID_RUT = " + rut + " GROUP BY SUBSTRING(CAST(ID_FECHA AS VARCHAR(6)),1,"
    # "4) ORDER BY SUBSTRING(CAST(ID_FECHA AS VARCHAR(6)),1,4) DESC")
    cursor.execute("SELECT Distinct SUBSTRING(CAST(ID_FECHA AS VARCHAR(6)),1,4) FROM BD_REMUNE.DBO.TA_BILLETAJE_PAGOS WHERE ID_RUT = " + rut)
    consulta = cursor.fetchall()
    cursor.close()
    annos = []
    for i, ano in enumerate(consulta):
        annos.append({
            'id': int(ano[0])
        })

    return jsonify(annos)


@app.route('/' + URI_API + '/generar_documento', methods=['POST'])
@jwt_required()
def generar_documento():
    if not request.args.get('mesInicio') or not request.args.get('annoInicio') or not request.args.get('mesTermino') or not request.args.get('annoTermino') or not request.args.get('rut') or not \
            request.args.get('censura'):
        return jsonify({'msg': 'Gracias por intentarlo !!'}), 404

    mes_inicio = str(formato_mes(request.args.get('mesInicio'))).strip()
    anno_inicio = str(request.args.get('annoInicio')).strip()
    mes_termino = str(formato_mes(request.args.get('mesTermino'))).strip()
    anno_termino = str(request.args.get('annoTermino')).strip()
    fecha_inicio = anno_inicio + "-" + mes_inicio
    fecha_termino = anno_termino + "-" + mes_termino
    rut = str(request.args.get('rut')).strip()
    censura = int(request.args.get('censura'))

    fi = datetime.date(datetime.strptime(fecha_inicio, '%Y-%m'))
    ft = datetime.date(datetime.strptime(fecha_termino, '%Y-%m'))

    if fi > ft:
        return jsonify({'number': 1, 'msg': 'La fecha de inicio no puede ser mayor a la fecha de termino.'}), 404

    try:
        directory = 'pdf_files'
        for f in os.listdir(directory):
            os.remove(os.path.join(directory, f))
    except Exception as error:
        return jsonify({'number': 3, 'msg': 'Problemas al limpiar carpeta', 'error': error}), 404

    try:
        liquidacion = liquidacionmes(rut, fecha_inicio, fecha_termino, censura)
        nombre_archivo = 'pdf_files/' + rut + '_' + str(hoy.strftime("%d%m%Y_%H%M%S")).strip() + '.pdf'
        liquidacion.output(nombre_archivo, dest='F').encode("latin-1")
        return send_file(nombre_archivo, as_attachment=True)
        # response = make_response(liquidacion.output(dest='S').encode("latin-1"))
        # response.headers.set('Content-Disposition', 'inline', filename=rut + '.pdf')
        # response.headers.set('Content-Type', 'application/pdf')
        # return response
    except Exception as error:
        return jsonify({'number': 2, 'msg': error}), 404


def formato_mes(mes):
    if int(mes) < 9:
        mes = "0" + mes
    return str(mes).strip()


@app.route('/' + URI_API + '/buscar_por_rut', methods=['POST'])
@jwt_required()
def buscar_por_rut():
    try:
        if not request.args.get('rut'):
            return jsonify({'msg': 'Debe indicar rut'}), 404
        else:
            rut = str(request.args.get('rut')).strip()
            conn = conectorbd()
            cursor = conn.cursor()
            cursor.execute("EXEC BD_REMUNE.dbo.sp_consultar_funcionario " + rut)
            datos_funcionario = cursor.fetchall()
            cursor.close()
            info = Funcionario.informacion(datos_funcionario)
            if info:
                return jsonify({'datosFuncionario': info}), 200
            else:
                return jsonify({'number': 1, 'msg': 'El rut ingresado, no se encuentra en nuestro registros.'}), 404

    except Exception as error:
        return jsonify({'error': error})


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/' + URI_API + '/upload_file', methods=['POST'])
@jwt_required()
def upload():
    if request.method == 'POST':
        # print('files', request.files)
        if 'file' not in request.files:
            return jsonify({'msg': 'No existe archivo'})
        f = request.files['file']
        if f.filename == '':
            return jsonify({'msg': 'Archivo no tiene nombre'})
        if f and allowed_file(f.filename):
            delete_files_in_directory('csv')
            filename = secure_filename(f.filename)
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            directory_path_liquidations = 'pdf_files'
            delete_files_in_directory(directory_path_liquidations)
            with open('csv/' + filename, newline='') as f:
                reader = csv.reader(f, delimiter=';', quoting=csv.QUOTE_NONE)
                # next(reader, None) # Salto la cabecera
                notes = list(reader)
                # print(notes)
                with open("pdf_files/observaciones.csv", "w", newline="") as csvoutput:
                    writer = csv.writer(csvoutput, delimiter=";")
                    headers = ["FOLIO", "RUT", "FECHA DESDE", "FECHA HASTA", "OBSERVACIONES"]
                    writer.writerow(i for i in headers)
                    for note in notes:
                        folio = str(re.sub(r'[^0-9]', '', str(note[0]).strip())).strip()
                        rut = str(re.sub(r'[^0-9]', '', str(note[1]).strip())).strip()
                        desde = str(note[2]).strip()
                        hasta = str(note[3]).strip()
                        # print(folio, rut, desde, hasta)
                        result = liquidacion_mes(rut, desde, hasta, 1, folio)
                        # print('result', result)
                        observaciones = [folio, rut, desde, hasta, result]
                        writer.writerow(observaciones)

            # genero archivo .zip

            for folder, subfolders, files in os.walk('pdf_files'):
                if files:
                    archivos_zip = zipfile.ZipFile('pdf_files/liquidaciones_p9.zip', 'w')
                    for file in files:
                        if file.endswith('.pdf') or file.endswith('.csv'):
                            # print(file)
                            archivos_zip.write(os.path.join(folder, file), os.path.relpath(os.path.join(folder, file), 'pdf_files'), compress_type=zipfile.ZIP_DEFLATED)

            archivos_zip.close()
            return send_file('pdf_files/liquidaciones_p9.zip', as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=4001)
