package br.com.finance.FinancePro.financias.Valor.Model;


import jakarta.persistence.*;

import java.util.List;


@Entity
@Table(name = "tb_valores")
public class ValoresModel  {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private long id;
    private int Entrada;
    private int Saida;
    private int ValorTot;


    public ValoresModel() {
    }

    public ValoresModel(long id, int entrada, int saida, int valorTot) {
        this.id = id;
        Entrada = entrada;
        Saida = saida;
        ValorTot = ValorTot;
    }

    public long getId() {
        return id;
    }

    public void setId(long id) {
        this.id = id;
    }

    public int getEntrada() {
        return Entrada;
    }

    public void setEntrada(int entrada) {
        Entrada = entrada;
    }

    public int getSaida() {
        return Saida;
    }

    public void setSaida(int saida) {
        Saida = saida;
    }

    public int getValorTot() {
        return ValorTot = this.Entrada-this.Saida;
    }
}
